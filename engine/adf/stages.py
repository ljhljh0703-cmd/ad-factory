"""단계 모음. 단계 하나 = 함수 하나 = 작업 하나.

예전 스크립트(judge.py, generate.py, footage_check.py, ua/*)는 그대로 두고 여기서 부른다.
그래야 검증해 둔 판정·채점 결과가 엔진으로 옮겨도 바뀌지 않는다(회귀 검사로 확인).
단계는 다시 돌려도 같은 결과가 나오게 쓴다. 외부 응답을 기다리다 이어 가면 처음부터 다시 돌기 때문이다.
"""
import os, json, subprocess, importlib.util, contextlib, io

from . import paths, providers
from .jobs import Blocked, Wait

REGISTRY = {}


def stage(name):
    def deco(fn):
        REGISTRY[name] = fn; fn.stage_name = name; return fn
    return deco


_mods = {}


def legacy(name, rel):
    """예전 스크립트를 모듈로 읽는다(print 출력은 작업 기록으로 보낸다)."""
    if name not in _mods:
        spec = importlib.util.spec_from_file_location("legacy_" + name, paths.p(rel))
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); _mods[name] = m
    return _mods[name]


def quiet(job, fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = fn(*a, **k)
    if buf.getvalue().strip():
        job.log(buf.getvalue().strip()[:4000])
    return r


def sh(job, cmd, cwd=None, timeout=3600):
    job.log("$ " + " ".join(str(c) for c in cmd))
    r = subprocess.run([str(c) for c in cmd], cwd=cwd or paths.ROOT, capture_output=True, text=True, timeout=timeout)
    if r.stdout.strip(): job.log(r.stdout.strip()[-4000:])
    if r.returncode != 0:
        raise RuntimeError(f"명령 실패({r.returncode}): {r.stderr.strip()[-1500:]}")
    return r.stdout


# ───────────── 대본 생성 ─────────────
@stage("대본.요청문")
def gen_build(job, run, per_type=2, game="jelly-panic"):
    g = legacy("generate", "generator/generate.py")
    quiet(job, g.build, run, per_type, game)
    for f, r in [(g.facts_path(game), "사실표"), (g.CRITERIA, "기준표")]: job.input(f, r)
    job.output(paths.p("generator", "runs", run, "prompt.md"), "요청문")
    return {"회차": run, "게임": game}


@stage("대본.생성")
def gen_llm(job, run, model="claude-sonnet-5-5", provider=None, replay=None):
    d = paths.p("generator", "runs", run)
    prompt = open(os.path.join(d, "prompt.md"), encoding="utf-8").read()
    pv = providers.pick(provider, {"raw": replay} if replay else None)
    text = pv.complete(job, "raw", prompt, model)
    open(os.path.join(d, "raw.jsonl"), "w", encoding="utf-8").write(text)
    job.output(os.path.join(d, "raw.jsonl"), "AI 원문(손대지 않음)")
    return {"회차": run, "글자": len(text)}


@stage("대본.받기")
def gen_ingest(job, run):
    g = legacy("generate", "generator/generate.py")
    quiet(job, g.ingest, run)
    d = paths.p("generator", "runs", run)
    job.input(os.path.join(d, "raw.jsonl"), "AI 원문")
    job.output(os.path.join(d, "candidates.jsonl"), "후보 대본")
    rep = json.load(open(os.path.join(d, "ingest-report.json"), encoding="utf-8"))
    return {k: rep[k] for k in ("받은 줄", "형식 통과", "형식 문제")}


# ───────────── 심사 ─────────────
@stage("심사.요청문")
def judge_prompt(job, run, set="dev", game=None):
    j = legacy("judge", "judge/judge.py")
    game = game or j.set_game(set)
    quiet(job, j.prompt, run, set, game)
    for f, r in [("CRITERIA.md", "기준표"), (f"game/{game}.json", "사실표"), (f"judge/prompts/{j.PROMPT_VER}.md", "요청문 틀")]:
        job.input(paths.p(f), r)
    d = paths.p("judge", "runs", run)
    job.output(os.path.join(d, "prompt.md"), "요청문"); job.output(os.path.join(d, "rules.jsonl"), "① 규칙 결과")
    return {"회차": run, "묶음": set, "게임": game}


@stage("심사.AI판정")
def judge_llm(job, run, times=2, model="claude-sonnet-5-5", provider=None, replay_from=None):
    """replay_from: 예전 회차 이름. 그 회차의 llm-N.jsonl 을 그대로 다시 쓴다(돈 안 씀)."""
    d = paths.p("judge", "runs", run)
    prompt = open(os.path.join(d, "prompt.md"), encoding="utf-8").read()
    replay = {f"llm-{i}": paths.p("judge", "runs", replay_from, f"llm-{i}.jsonl") for i in range(1, times + 1)} if replay_from else None
    pv = providers.pick(provider, replay)
    waiting = []
    for i in range(1, times + 1):
        try:
            text = pv.complete(job, f"llm-{i}", prompt, model)
        except Wait as w:
            waiting.append(str(w)); continue
        open(os.path.join(d, f"llm-{i}.jsonl"), "w", encoding="utf-8").write(text)
    if waiting:
        raise Wait("외부응답대기", " / ".join(waiting))
    meta = json.load(open(os.path.join(d, "run.json"), encoding="utf-8"))
    meta.update({"모델": model, "판정_횟수": times, "제공자": pv.name})
    json.dump(meta, open(os.path.join(d, "run.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for i in range(1, times + 1): job.output(os.path.join(d, f"llm-{i}.jsonl"), f"AI 판정 {i}회(원문)")
    return {"회차": run, "판정_횟수": times, "제공자": pv.name}


@stage("심사.합치기")
def judge_combine(job, run):
    j = legacy("judge", "judge/judge.py")
    quiet(job, j.combine, run)
    d = paths.p("judge", "runs", run)
    out = os.path.join(d, "decisions.jsonl"); job.output(out, "최종 판정")
    rows = [json.loads(l) for l in open(out, encoding="utf-8") if l.strip()]
    cnt = {}
    for r in rows: cnt[r["최종"]] = cnt.get(r["최종"], 0) + 1
    return {"회차": run, "최종": cnt}


@stage("심사.채점")
def judge_score(job, run, block_on_expensive=False):
    j = legacy("judge", "judge/judge.py")
    quiet(job, j.score, run)
    f = paths.p("judge", "runs", run, "score.json"); job.output(f, "채점")
    s = json.load(open(f, encoding="utf-8"))
    res = {k: s[k] for k in ("묶음", "소재_수", "판정_일치", "반려_재현율", "카파", "비싼_오류(반려를_통과시킴)")}
    if block_on_expensive and s["비싼_오류(반려를_통과시킴)"]:
        raise Blocked(f"비싼 오류 {len(s['비싼_오류(반려를_통과시킴)'])}건: {', '.join(s['비싼_오류(반려를_통과시킴)'])}")
    return res


# ───────────── 녹화본 대조 ─────────────
@stage("대조.시트")
def footage_sheets(job, video, out, fps=1):
    f = legacy("footage", "verify/footage_check.py")
    os.makedirs(paths.p(out), exist_ok=True)
    quiet(job, f.sheets, paths.p(video), paths.p(out), fps)
    job.input(paths.p(video), "영상")
    meta = json.load(open(paths.p(out, "sheets.json")))
    for s in meta["sheets"]: job.output(s, "시트")
    return {"프레임": meta["frames"], "시트": len(meta["sheets"])}


@stage("대조.판정")
def footage_judge(job, script, out, final=False, model="claude-sonnet-5-5", provider=None, replay=None):
    f = legacy("footage", "verify/footage_check.py")
    quiet(job, f.prompt, paths.p(script), paths.p(out), final)
    job.input(paths.p(script), "대본")
    prompt = open(paths.p(out, "prompt.md"), encoding="utf-8").read()
    sheets = json.load(open(paths.p(out, "sheets.json")))["sheets"]
    pv = providers.pick(provider, {"answer": paths.p(replay)} if replay else None)
    text = pv.complete(job, "answer", prompt, model, images=sheets)
    open(paths.p(out, "answer.jsonl"), "w", encoding="utf-8").write(text)
    quiet(job, f.report, paths.p(out))
    rep = json.load(open(paths.p(out, "report.json")))
    job.output(paths.p(out, "report.json"), "대조 결과")
    if rep["결론"] != "통과":
        raise Wait("사람확인대기", f"다름 {rep['다름']} · 없음 {rep['없음']}: 사람 확인 대기열로")
    return {k: rep[k] for k in ("컷_수", "맞음", "편집", "다름", "없음", "결론")}


# ───────────── 사실표 자동 대조 ─────────────
@stage("사실표.대조")
def facts_check(job, game="jelly-panic", fresh=True):
    """공개판 소스와 사실표를 맞춰 보고, 어긋나면 막는다(뒤 심사 단계가 돌지 않음). fresh면 공개판에서 소스를 새로 받는다."""
    from . import factcheck
    ad = paths.p("adapters", game)
    if fresh and not os.path.isdir(json.load(open(os.path.join(ad, "adapter.json"), encoding="utf-8"))["사실표"]["출처"].get("저장소_경로") or ""):
        job.log(f"공개판 소스 새로 받기: {factcheck.refresh_cache(ad)}")
    man = json.load(open(os.path.join(ad, "adapter.json"), encoding="utf-8"))
    facts = paths.p(man["사실표"]["파일"])
    rep, ex = factcheck.compare(ad, facts)
    out = os.path.join(job.dir, "factcheck.json")
    json.dump({**rep, "뽑은_원문": ex}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    job.input(facts, "사실표")
    for f in ex["파일"]: job.input(os.path.join(factcheck.source_dir(ad, man), f), "공개판 소스")
    job.output(out, "대조 결과")
    if rep["결론"] != "통과":
        raise Blocked(f"사실표 어긋남 {len(rep['어긋남'])}건: " + " / ".join(i["종류"] for i in rep["어긋남"][:4]))
    return {"사실표_판": rep["사실표_판"], "뽑은_것": rep["뽑은_것"]}


# ───────────── 사람 검토 ─────────────
@stage("검토.넣기")
def review_enqueue(job, run):
    """심사 회차의 「사람 확인」을 사람 검토 대기열로 보낸다."""
    from . import review
    made = review.from_judge_run(run)
    return {"넣음": [m["id"] for m in made], "대기열": review.stats()}


# ───────────── 성과 보고 ─────────────
@stage("성과.주간보고")
def perf_report(job, events_dir, platform_csv=None, period="", note="", model="claude-sonnet-5-5", provider=None, ai=True):
    """수집기 기록(+플랫폼 통계)을 광고별로 묶고 소재 피로를 보고, AI가 문제/해결/다음 보고를 쓴다."""
    from . import perf
    ev = perf.load_events(paths.p(events_dir)); pf = perf.load_platform(paths.p(platform_csv) if platform_csv else None)
    table, fat = perf.by_ad(ev), perf.fatigue(pf, ev)
    out = os.path.join(job.dir, "metrics.json")
    json.dump({"기간": period, "메모": note, "광고별": table, "피로": fat, "기록_수": len(ev), "플랫폼_행": len(pf)}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    job.input(paths.p(events_dir), "익명 기록"); job.output(out, "광고별 지표")
    res = {"기록_수": len(ev), "광고": list(table), "피로_의심": [a for a, f in fat.items() if f["판단"].startswith("피로")]}
    if ai:
        text = providers.pick(provider).complete(job, "report", perf.report_prompt(table, fat, period, note), model)
        open(os.path.join(job.dir, "report.md"), "w", encoding="utf-8").write(text); job.output(os.path.join(job.dir, "report.md"), "AI 주간 보고")
    return res


# ───────────── 대화형 기획 ─────────────
@stage("기획.명세")
def plan_spec(job, text, run=None, model="claude-sonnet-5-5", provider=None, auto=False):
    """말로 쓴 요청 → 캠페인 명세 → 규칙 검사. 빠진 값이 있으면 질문을 남기고 사람 확인을 기다린다."""
    from . import plan
    raw = providers.pick(provider).complete(job, "spec", plan.prompt(text), model)
    spec = plan.parse(raw); chk = plan.check(spec, text)
    f = os.path.join(job.dir, "spec.json")
    json.dump({"요청": text, "명세": spec, "검사": chk}, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    job.output(f, "캠페인 명세")
    if chk["진행"] and auto and run:
        return {"명세": spec, "검사": chk, "넣은_작업": plan.enqueue(spec, run)}
    if chk["물어볼_것"]:
        return {"명세": spec, "검사": chk, "다음": "질문에 답하면 명세를 고쳐 다시 넣습니다"}
    return {"명세": spec, "검사": chk}


@stage("성과.받기")
def perf_pull(job, out="runs/events", days=7):
    """수집기에서 최근 며칠 기록을 내려받는다(시험 기록 src=test 는 보고에서 빠짐)."""
    import datetime as dt
    from . import perf
    ds = [(dt.datetime.utcnow().date() - dt.timedelta(days=k)).isoformat() for k in range(int(days))][::-1]
    got = perf.pull(paths.p(out), ds)
    for d in ds: job.output(paths.p(out, f"{d}.jsonl"), f"기록 {d}")
    return {"날짜별_줄": got}
