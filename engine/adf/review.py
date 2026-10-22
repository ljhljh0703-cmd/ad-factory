"""사람 검토 대기열.

AI가 「사람 확인」으로 넘긴 것(심사 두 판정이 엇갈림, AI가 확인 요청, 녹화본 대조에서 다름·없음)과
사람이 AI 판정을 뒤집고 싶은 것을 한 줄로 모은다. 결정마다 이유를 꼭 적게 하고,
결정된 소재는 정답 꼬리표를 붙여 평가셋 후보(eval/review/review.jsonl)로 보낸다.
평가셋 후보는 다음 회귀 검사부터 함께 돈다(숨긴 묶음과 섞지 않는다).
"""
import json, os, glob, datetime

from . import paths

DECISIONS = ("통과", "반려")


def qdir():
    d = paths.p("runs", "review"); os.makedirs(d, exist_ok=True); return d


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _path(rid):
    return os.path.join(qdir(), rid + ".json")


def items(state=None):
    out = []
    for p in sorted(glob.glob(os.path.join(qdir(), "Q*.json"))):
        it = json.load(open(p, encoding="utf-8"))
        if state is None or it["상태"] == state: out.append(it)
    return out


def add(kind, source, subject, payload, ai_verdict=None, why=""):
    """같은 출처·같은 소재가 이미 있으면 새로 넣지 않는다."""
    for it in items():
        if it["출처"] == source and it["소재"] == subject: return it
    n = 1 + max([int(os.path.basename(p)[1:-5]) for p in glob.glob(os.path.join(qdir(), "Q*.json"))] or [0])
    it = {"id": f"Q{n:04d}", "종류": kind, "출처": source, "소재": subject, "AI_판정": ai_verdict, "AI_이유": why,
          "내용": payload, "상태": "대기", "결정": None, "조건": [], "이유": None, "처리자": None, "넣은_때": now(), "처리한_때": None}
    json.dump(it, open(_path(it["id"]), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return it


def decide(rid, decision, reason, rules=None, who="작가"):
    if decision not in DECISIONS: raise ValueError(f"결정은 {DECISIONS} 중 하나")
    if not reason or len(reason.strip()) < 4: raise ValueError("이유를 적어야 합니다(평가셋 꼬리표로 남음)")
    if decision == "반려" and not rules: raise ValueError("반려는 걸린 조건(R1 등)을 하나 이상 적어야 합니다")
    it = json.load(open(_path(rid), encoding="utf-8"))
    it.update({"상태": "처리", "결정": decision, "조건": rules or [], "이유": reason.strip(), "처리자": who, "처리한_때": now()})
    it["뒤집음"] = it["AI_판정"] in DECISIONS and it["AI_판정"] != decision
    it["비싼_오류"] = it["AI_판정"] == "통과" and decision == "반려"
    json.dump(it, open(_path(rid), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if it["종류"] == "심사": _to_evalset(it)
    return it


def _to_evalset(it):
    d = paths.p("eval", "review"); os.makedirs(d, exist_ok=True)
    f = os.path.join(d, "review.jsonl")
    rows = [json.loads(l) for l in open(f, encoding="utf-8")] if os.path.exists(f) else []
    rid = f"V-{it['소재']}"
    rows = [r for r in rows if r["id"] != rid]
    src = dict(it["내용"]); src.pop("id", None)
    rows.append({"id": rid, **src, "정답": it["결정"], "걸린것": it["조건"], "메모": it["이유"], "출처": f"사람 검토 {it['id']} ({it['출처']})",
                 "경계": bool(it.get("뒤집음")), "나눔": "review"})
    with open(f, "w", encoding="utf-8") as fh:
        for r in rows: fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def from_judge_run(run):
    """심사 회차의 「사람 확인」을 대기열로. 평가셋 회차는 정답이 이미 있어 넣지 않는다."""
    d = paths.p("judge", "runs", run)
    meta = json.load(open(os.path.join(d, "run.json"), encoding="utf-8"))
    if meta["set"] in ("dev", "holdout", "holdout2", "review"): return []
    cands = {}
    f = paths.p("generator", "runs", meta["set"], "candidates.jsonl")
    if os.path.exists(f):
        cands = {c["id"]: c for c in (json.loads(l) for l in open(f, encoding="utf-8") if l.strip())}
    made = []
    for l in open(os.path.join(d, "decisions.jsonl"), encoding="utf-8"):
        o = json.loads(l)
        if o["최종"] != "사람 확인": continue
        why = " / ".join(x.get("사람확인_이유") or x.get("사유", "") for x in o["근거"] if x.get("사람확인_이유") or x.get("사유"))
        made.append(add("심사", f"심사 {run}", o["id"], cands.get(o["id"], {"id": o["id"]}), ai_verdict="사람 확인", why=f"{o['경로']}: {why}"))
    return made


def override(run, cid, decision, reason, rules=None, who="작가"):
    """AI가 통과·반려로 끝낸 소재를 사람이 뒤집는다. 대기열에 넣고 바로 처리한다."""
    d = paths.p("judge", "runs", run)
    meta = json.load(open(os.path.join(d, "run.json"), encoding="utf-8"))
    dec = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(d, "decisions.jsonl"), encoding="utf-8")}
    f = paths.p("generator", "runs", meta["set"], "candidates.jsonl")
    cands = {c["id"]: c for c in (json.loads(l) for l in open(f, encoding="utf-8") if l.strip())} if os.path.exists(f) else {}
    it = add("심사", f"심사 {run}", cid, cands.get(cid, {"id": cid}), ai_verdict=dec[cid]["최종"], why=dec[cid]["경로"])
    return decide(it["id"], decision, reason, rules, who)


def stats():
    its = items(); done = [i for i in its if i["상태"] == "처리"]
    return {"대기": len(its) - len(done), "처리": len(done), "뒤집음": sum(1 for i in done if i.get("뒤집음")),
            "비싼_오류_찾음": sum(1 for i in done if i.get("비싼_오류")),
            "평가셋_후보": sum(1 for _ in open(paths.p("eval", "review", "review.jsonl"), encoding="utf-8")) if os.path.exists(paths.p("eval", "review", "review.jsonl")) else 0}
