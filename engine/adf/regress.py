"""회귀 감시: 심사 결과를 바꿀 수 있는 것(기준표, 사실표, 요청문 틀, 규칙 코드, 모델)이 바뀌면
평가셋 심사를 다시 돌리고, 비싼 오류(반려를 통과시킴)가 하나라도 나오면 막는다.

- 늘 도는 묶음: dev, review(사람 검토에서 넘어온 것)
- 숨긴 묶음(holdout, holdout2)은 바뀔 때마다 돌리지 않는다. 자주 보면 숨긴 묶음에 맞춰 고치게 되기 때문.
  모델을 바꾸거나 배포 전에만 release=true 로 한 번 돌린다.
"""
import json, os, hashlib, datetime, re

from . import paths, jobs, pipelines

WATCH = {
    "기준표": "CRITERIA.md",
    "요청문_틀": "judge/prompts/judge-v1.md",
    "규칙_코드": "judge/judge.py",
}


def _h(path):
    return hashlib.sha256(open(paths.p(path), "rb").read()).hexdigest()[:12] if os.path.exists(paths.p(path)) else None


def fingerprint(game="jelly-panic", model="claude-sonnet-5-5"):
    man = json.load(open(paths.p("adapters", game, "adapter.json"), encoding="utf-8"))
    fp = {k: _h(v) for k, v in WATCH.items()}
    fp["사실표"] = _h(man["사실표"]["파일"]); fp["모델"] = model
    rv = paths.p("eval", "review", "review.jsonl")
    fp["검토_묶음"] = _h("eval/review/review.jsonl") if os.path.exists(rv) else None
    return fp


def sdir():
    d = paths.p("runs", "regress"); os.makedirs(d, exist_ok=True); return d


def state():
    f = os.path.join(sdir(), "state.json")
    return json.load(open(f, encoding="utf-8")) if os.path.exists(f) else {"기준": None, "회차": []}


def save_state(s):
    json.dump(s, open(os.path.join(sdir(), "state.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def check(game="jelly-panic", model="claude-sonnet-5-5", provider=None, release=False, force=False):
    """바뀐 것이 있으면 회귀 회차를 대기열에 넣는다. 돌려준 값: 바뀐 것과 넣은 작업."""
    s = state(); fp = fingerprint(game, model)
    last = s["회차"][-1]["지문"] if s["회차"] else None
    changed = [k for k in fp if not last or fp[k] != last.get(k)]
    if not changed and not force and not release:
        return {"바뀐_것": [], "넣은_작업": []}
    n = sum(1 for r in s["회차"] if r["묶음"]) + 1; rid = f"G{n:03d}"
    sets = ["dev"] + (["review"] if fp["검토_묶음"] else []) + (["holdout", "holdout2"] if release else [])
    made = []
    for st in sets:
        run = f"{rid}-{st}"
        js = pipelines.enqueue("심사", {"game": game, "run": run, "set": st, "model": model, "provider": provider,
                                        "block_on_expensive": True}, note=f"회귀 {rid}")
        made.append({"묶음": st, "회차": run, "작업": [j.id for j in js]})
    s["회차"].append({"id": rid, "때": datetime.datetime.now().isoformat(timespec="seconds"), "지문": fp, "바뀐_것": changed,
                     "숨긴_묶음_포함": release, "묶음": made, "결과": None})
    save_state(s)
    return {"회귀": rid, "바뀐_것": changed, "넣은_작업": made}


def collect():
    """회귀 회차마다 채점 결과를 모으고 막음 여부를 정한다."""
    s = state(); idx = {j.id: j for j in jobs.all_jobs()}
    prev_ok = None
    for r in s["회차"]:
        if not r["묶음"]:  # 기준점(엔진 이전 회차)
            prev_ok = r["결과"]["묶음별"]; continue
        res, gate, pending = {}, "통과", False
        for m in r["묶음"]:
            last = idx.get(m["작업"][-1]); first = idx.get(m["작업"][0])
            states = [idx[j].d["상태"] if j in idx else "?" for j in m["작업"]]
            if "막음" in states:
                gate = "막음"
                blk = next(idx[j] for j in m["작업"] if idx[j].d["상태"] == "막음")
                res[m["묶음"]] = {"상태": "막음", "단계": blk.d["단계"], "이유": blk.d["결과"]}
                f = paths.p("judge", "runs", m["회차"], "score.json")
                if os.path.exists(f): res[m["묶음"]].update(_score(f))
            elif all(x == "완료" for x in states):
                res[m["묶음"]] = {"상태": "완료", **_score(paths.p("judge", "runs", m["회차"], "score.json"))}
            else:
                pending = True; res[m["묶음"]] = {"상태": "진행", "작업_상태": states}
                if "실패" in states: gate = "실패"
        if pending and gate == "통과": gate = "진행"
        # 앞 회차 대비 변화
        if prev_ok and "dev" in res and "판정_일치" in res["dev"] and "판정_일치" in prev_ok.get("dev", {}):
            res["dev"]["앞_회차_대비"] = round(res["dev"]["판정_일치"] - prev_ok["dev"]["판정_일치"], 3)
        r["결과"] = {"관문": gate, "묶음별": res}
        if gate == "통과": prev_ok = res
    save_state(s)
    return s


def _score(f):
    sc = json.load(open(f, encoding="utf-8"))
    return {k: sc[k] for k in ("소재_수", "판정_일치", "반려_재현율", "카파", "사람_확인_비율", "비싼_오류(반려를_통과시킴)", "통과를_반려함")}


def baseline(run, factsheet_file=None, note=""):
    """이미 있는 심사 회차를 기준점으로 등록한다(엔진을 만들기 전 회차를 이어 붙일 때)."""
    s = state(); fp = fingerprint()
    if factsheet_file: fp["사실표"] = hashlib.sha256(open(factsheet_file, "rb").read()).hexdigest()[:12]
    fp["검토_묶음"] = None
    meta = json.load(open(paths.p("judge", "runs", run, "run.json"), encoding="utf-8"))
    s["회차"].insert(0, {"id": "G000", "때": meta.get("만든_때"), "지문": fp, "바뀐_것": [], "숨긴_묶음_포함": False, "메모": note,
                        "묶음": [], "결과": {"관문": "통과", "묶음별": {meta["set"]: {"상태": "완료", "회차": run, **_score(paths.p("judge", "runs", run, "score.json"))}}}})
    save_state(s); return s["회차"][0]
