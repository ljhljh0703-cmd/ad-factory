"""심사 품질 관리: 정답 묶음의 틀린 종류별 비용, 판정 흔들림, 자동 통과분 사람 재검, 회차 사이 변화.

설정은 judge/quality.json(없으면 아래 기본값). 비용 가중치와 재검 비율은 작가가 바꿀 수 있는 값이다.
"""
import os, json, glob, hashlib, math
from . import paths
from .stats import wilson, upper_zero, r

DEFAULT = {
    # 정답 → 판정 칸마다 소재 하나가 치르는 비용. 반려해야 할 것을 통과시키면 가장 비싸다.
    "비용": {"반려→통과": 10, "반려→사람 확인": 1, "통과→반려": 2, "통과→사람 확인": 0.5,
            "사람 확인→통과": 3, "사람 확인→반려": 0.5},
    "재검_비율": 0.2,          # 사람 판정이 없는 자동 통과분 중 사람이 다시 볼 비율
    "재검_최소": 1,            # 회차마다 최소 몇 개
    "신뢰수준": 0.95,
}

LABELS = ("통과", "반려", "사람 확인")


def config():
    p = paths.p("judge", "quality.json")
    cfg = json.loads(json.dumps(DEFAULT))
    if os.path.exists(p):
        user = json.load(open(p, encoding="utf-8"))
        for k, v in user.items():
            if isinstance(v, dict): cfg.setdefault(k, {}).update(v)
            else: cfg[k] = v
    return cfg


def _ci(k, n, conf):
    lo, hi = wilson(k, n, conf)
    return [r(lo), r(hi)]


def _lines(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if os.path.exists(p) else []


def gold_quality(run_meta, score, cfg):
    """정답 붙인 회차 하나: 틀린 종류별 수와 비용, 반려 놓침의 위쪽 한계."""
    cm = score.get("혼동표(정답→판정)") or {}
    conf = cfg["신뢰수준"]
    n = sum(sum(row.values()) for row in cm.values())
    cost = 0.0; errors = {}
    for g, row in cm.items():
        for d, c in row.items():
            if g == d or not c: continue
            key = f"{g}→{d}"; errors[key] = c
            cost += c * cfg["비용"].get(key, 1)
    rej = sum((cm.get("반려") or {}).values())
    caught = (cm.get("반려") or {}).get("반려", 0)
    missed = (cm.get("반려") or {}).get("통과", 0)
    ok = (cm.get("통과") or {})
    passes = sum(ok.values())
    # 반려를 「잡아야 할 쪽」으로 둔 정밀도와 informedness(재현율 + 특이도 - 1). 한쪽만 좋아진 변경을 막는 한 쌍
    flagged = sum((cm.get(g) or {}).get("반려", 0) for g in cm)
    rec = caught / rej if rej else None
    spec = 1 - ok.get("반려", 0) / passes if passes else None
    return {
        "회차": run_meta["run"], "묶음": run_meta["set"], "때": run_meta.get("만든_때"), "소재_수": n,
        "틀린_것": errors,
        "비용_합": r(cost, 2), "소재당_비용": r(cost / n, 3) if n else None,
        "반려_정답": rej, "반려_잡음": caught,
        "반려_재현율_구간": _ci(caught, rej, conf),
        # 놓친 반려가 0건이어도 진짜 놓침률은 이 값까지 있을 수 있다(정답 반려 수가 작을수록 크다)
        "반려_놓침률_위쪽": r(upper_zero(rej, conf)) if missed == 0 and rej else _ci(missed, rej, conf)[1],
        "과잉_차단": ok.get("반려", 0), "과잉_차단률_구간": _ci(ok.get("반려", 0), passes, conf),
        "반려_정밀도": r(caught / flagged) if flagged else None,
        "informedness": r(rec + spec - 1) if rec is not None and spec is not None else None,
        # 놓침률 위쪽 한계를 5% 아래로 말하려면 놓침 0건일 때 반려 정답이 이만큼 필요
        "반려_정답_필요": math.ceil(math.log(1 - conf) / math.log(0.95)),
    }


def flips(decisions):
    """두 번 판정한 소재 중 두 판정이 다른 비율. 규칙으로 끝난 소재는 AI가 판정하지 않으므로 뺀다."""
    two = [d for d in decisions if len(d.get("AI_판정") or []) >= 2]
    diff = [d["id"] for d in two if len(set(d["AI_판정"])) > 1]
    return len(two), diff


def audit_estimate(items, conf):
    """자동 통과 중 사람이 본 것에서 사람이 반려로 본 비율(= 자동 통과에 숨어 있는 놓친 반려 추정)."""
    seen = [i for i in items if i["최종"] == "통과" and i.get("사람")]
    bad = [i["id"] for i in seen if i["사람"]["판정"] == "반려"]
    return {"본_수": len(seen), "사람_반려": len(bad), "사람_반려_id": bad,
            "비율": r(len(bad) / len(seen)) if seen else None,
            "구간": _ci(len(bad), len(seen), conf) if seen else [None, None]}


def audit_plan(setname, items, cfg):
    """사람 판정이 없는 자동 통과분에서 정해진 비율만큼 다시 볼 소재를 고른다.

    고르는 순서는 회차 이름과 소재 id를 섞은 지문 순서라, 누가 언제 돌려도 같은 소재가 나온다(골라 보기 방지).
    """
    passed = [i for i in items if i["최종"] == "통과"]
    checked = [i for i in passed if i.get("사람")]
    need = max(cfg["재검_최소"], math.ceil(cfg["재검_비율"] * len(passed))) if passed else 0
    todo = max(0, need - len(checked))
    pool = sorted((i for i in passed if not i.get("사람")),
                  key=lambda i: hashlib.sha256(f"{setname}:{i['id']}".encode()).hexdigest())
    return {"자동_통과": len(passed), "사람이_본_것": len(checked), "목표": need,
            "더_볼_것": [i["id"] for i in pool[:todo]]}


def rule_candidates(reviews):
    """사람 검토가 AI 판정을 뒤집은 소재 = 기준표 문구가 애매할 수 있는 곳. 고칠지는 작가가 정한다."""
    return [{"검토": q["id"], "소재": q["소재"], "AI_판정": q.get("AI_판정"), "사람_결정": q.get("결정"),
             "조건": q.get("조건") or [], "비싼_오류": bool(q.get("비싼_오류"))}
            for q in reviews if q.get("상태") == "처리" and q.get("뒤집음")]


def build(allowed, generated, replays=(), reviews=()):
    """공개용 묶음의 「심사_품질」 칸. generated = export.generated() 결과."""
    cfg = config(); conf = cfg["신뢰수준"]
    gold, flip_rows = [], []
    for d in sorted(glob.glob(paths.p("judge", "runs", "*"))):
        mp = os.path.join(d, "run.json")
        if not os.path.exists(mp): continue
        m = json.load(open(mp, encoding="utf-8"))
        game = m.get("게임")
        if game is None:  # 옛 회차는 게임 칸이 없음 → 묶음의 게임
            rj = os.path.join(paths.p("generator", "runs", m["set"]), "run.json")
            game = json.load(open(rj, encoding="utf-8")).get("game", "jelly-panic") if os.path.exists(rj) else "jelly-panic"
        if game not in allowed or m["run"] in replays: continue
        sp = os.path.join(d, "score.json")
        if os.path.exists(sp):
            gold.append(gold_quality(m, json.load(open(sp, encoding="utf-8")), cfg))
        n2, diff = flips(_lines(os.path.join(d, "decisions.jsonl")))
        if n2:
            flip_rows.append({"회차": m["run"], "묶음": m["set"], "때": m.get("만든_때"), "두_번_판정": n2,
                              "엇갈림": len(diff), "엇갈린_id": diff, "구간": _ci(len(diff), n2, conf)})
    gold.sort(key=lambda x: x["때"] or ""); flip_rows.sort(key=lambda x: x["때"] or "")
    tot2 = sum(x["두_번_판정"] for x in flip_rows); totd = sum(x["엇갈림"] for x in flip_rows)

    sets = []
    prev = None
    for g in generated:
        items = g["소재"]; n = len(items)
        share = {lab: sum(i["최종"] == lab for i in items) for lab in LABELS}
        row = {"회차": g["회차"], "심사_회차": g["심사_회차"], "소재_수": n,
               "판정_수": share, "사람확인_구간": _ci(share["사람 확인"], n, conf),
               "재검_추정": audit_estimate(items, conf), "재검_계획": audit_plan(g["회차"], items, cfg)}
        # 앞 생성 회차와 사람 확인 비율 구간이 겹치지 않으면 「변화 큼」: 기준·사실표·생성기 중 무엇이 바뀌었는지 본다
        if prev and n and prev["소재_수"]:
            a, b = row["사람확인_구간"], prev["사람확인_구간"]
            row["앞_회차와_변화"] = "변화 큼" if (a[0] > b[1] or b[0] > a[1]) else "구간 안"
        sets.append(row); prev = row
    return {"설정": {"비용": cfg["비용"], "재검_비율": cfg["재검_비율"], "재검_최소": cfg["재검_최소"], "신뢰수준": conf},
            "정답_회차": gold, "흔들림": {"회차별": flip_rows, "두_번_판정": tot2, "엇갈림": totd,
                                       "구간": _ci(totd, tot2, conf)},
            "생성_회차": sets, "기준표_수정_후보": rule_candidates(reviews)}
