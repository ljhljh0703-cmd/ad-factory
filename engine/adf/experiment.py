"""소재 성과 실험: 미리 정한 지표와 판정 규칙으로 광고끼리 비교한다.

규칙은 ua/experiment.json 에 먼저 적고(사전 등록), 숫자를 본 뒤에 바꾸지 않는다. 바꾸면 판을 올리고 그때부터 다시 센다.
근거와 출처는 볼트 wiki/projects/design-aesthetic-returns/2026-10-23-app-web-flow/F-experiment.md.
- 세는 단위는 광고 링크로 들어온 사람 1명(판 단위로 세면 한 사람이 여러 판을 해서 구간이 실제보다 좁아진다).
- 주 지표 하나로만 「더 낫다」를 말한다. 안전 지표가 나쁘면 앞서도 확정하지 않는다. 보조 지표는 이유를 찾는 데만 쓴다.
- 판정은 미리 정한 시점(들어온 사람 60명·120명·필요 표본)에서만 하고, 시점마다 기준을 낮춰(1.8%) 중간에 들여다본 효과를 막는다.
- 비교는 「광고 하나 대 나머지 광고 합산」으로 하고 홈 방식으로 보정한다.
- 결과는 확정 / 방향 / 보류 / 결론 없음 네 칸.
"""
import os, json, collections, random
from . import paths, perf
from .stats import wilson, n_per_arm, two_prop_p, holm, r

DEFAULT = {
    "판": 1,
    "주_지표": {"이름": "첫 수 둔 비율", "분자": "첫 판에서 첫 수를 둔 사람", "분모": "광고 링크로 들어와 첫 판을 연 사람"},
    "보조_지표": ["다시 하기 비율", "첫 수까지 초(중앙값)", "채널별 첫 수 둔 비율"],
    "안전_지표": [{"이름": "다시 하기 비율", "기준": "앞선 광고의 95% 구간 위쪽 끝이 전체 평균보다 낮으면 확정 보류"}],
    "기준값": 0.5,             # 실제 값이 쌓이기 전 가정. 50%로 두면 필요한 표본이 가장 크게 잡혀 안전한 쪽. 첫 2주 평균으로 바꾼다
    "최소_감지_차이": 0.15,     # 이만큼(절대 %p) 차이 나야 찾겠다는 약속
    "유의수준": 0.05,
    "검정력": 0.8,
    "판정_시점": [60, 120],     # 들어온 사람 수. 마지막 시점은 필요 표본
    "시점_기준": 0.018,         # 세 번 들여다볼 때 전체 오탐을 5%로 묶는 시점별 기준
    "방향_최소": 30,            # 이보다 적으면 보류(방향도 적지 않음)
    "최소_날_수": 7,            # 요일 효과 때문에 확정 전에 채울 날 수
    "피로": {"창": 7, "유입_비율": 0.5, "첫수_하락": 0.10},
}


def plan():
    p = paths.p("ua", "experiment.json")
    cfg = json.loads(json.dumps(DEFAULT))
    if os.path.exists(p): cfg.update(json.load(open(p, encoding="utf-8")))
    return cfg


def ad_of(requests):
    """링크 꼬리표 ad 값(소재 id 또는 광고 이름) → 광고 이름."""
    m = {}
    for q in requests:
        m[q["광고"]] = q["광고"]
        if q.get("소재"): m[q["소재"]] = q["광고"]
    return m


def counts(events, mapping):
    """광고별·채널별 들어온 사람, 첫 수 둔 사람, 끝난 판, 다시 하기."""
    by = collections.defaultdict(lambda: {"들어옴": set(), "첫수": set(), "끝": 0, "다시": 0, "초": [], "날": set()})
    for e in events:
        ad = mapping.get(e.get("ad"))
        if not ad: continue  # 우리 광고 꼬리표가 아닌 기록(직접 들어옴, 시험)은 뺀다
        for key in ((ad, e.get("src") or "?"), (ad, "*")):
            b = by[key]; b["날"].add(e.get("day"))
            if e["type"] == "start" and e.get("n") == 0: b["들어옴"].add(e["sid"])
            elif e["type"] == "first_move": b["첫수"].add(e["sid"]); b["초"].append(e.get("after"))
            elif e["type"] == "end": b["끝"] += 1
            elif e["type"] == "restart": b["다시"] += 1
    return by


def p_best(rows, draws=4000, seed=7):
    """광고마다 주 지표가 가장 높을 확률(베타 분포에서 뽑기, 씨앗 고정). 다음 재게시 자리를 이 비율로 나눈다."""
    if not rows: return {}
    rnd = random.Random(seed); win = collections.Counter()
    for _ in range(draws):
        v = {x["광고"]: rnd.betavariate(x["첫수"] + 1, x["들어옴"] - x["첫수"] + 1) for x in rows}
        win[max(v, key=v.get)] += 1
    return {x["광고"]: r(win[x["광고"]] / draws) for x in rows}


def fatigue(events, mapping, cfg):
    """두 신호가 같이 올 때만 피로: 최근 창의 하루 유입이 첫 창의 절반 아래 + 첫 수 비율이 10%p 넘게 떨어짐.
    유기 게시는 올린 직후 몰리고 자연히 줄어서 유입 하나로는 판정하지 않는다."""
    f = cfg["피로"]; w = f["창"]
    days = collections.defaultdict(lambda: collections.defaultdict(lambda: [set(), set()]))
    for e in events:
        ad = mapping.get(e.get("ad"))
        if not ad: continue
        if e["type"] == "start" and e.get("n") == 0: days[ad][e["day"]][0].add(e["sid"])
        elif e["type"] == "first_move": days[ad][e["day"]][1].add(e["sid"])
    out = {}
    for ad, dd in days.items():
        ds = sorted(dd)
        if len(ds) < 2 * w:
            out[ad] = {"판단": f"날 수 부족({len(ds)}일, {2 * w}일부터 봄)"}; continue

        def win(sl):
            n = sum(len(dd[d][0]) for d in sl); k = sum(len(dd[d][1] & dd[d][0]) for d in sl)
            return n / len(sl), (k / n if n else None)
        (n0, p0), (n1, p1) = win(ds[:w]), win(ds[-w:])
        s1 = n0 > 0 and n1 < f["유입_비율"] * n0
        s2 = p0 is not None and p1 is not None and p1 < p0 - f["첫수_하락"]
        out[ad] = {"첫_창_하루_유입": r(n0, 1), "최근_창_하루_유입": r(n1, 1), "첫_창_첫수": r(p0), "최근_창_첫수": r(p1),
                   "판단": "피로 의심: 휴식으로 두고 2~4주 뒤 색·문구만 바꾼 변형으로 다시" if s1 and s2 else
                           ("신호 하나만: 지켜봄" if s1 or s2 else "괜찮음")}
    return out


def evaluate(events, requests, cfg=None, days=None):
    cfg = cfg or plan()
    mapping = ad_of(requests)
    by = counts(events, mapping)
    ads = sorted({ad for ad, ch in by if ch == "*"})
    need = n_per_arm(cfg["기준값"], cfg["최소_감지_차이"], cfg["유의수준"], cfg["검정력"], k=max(1, len(ads)))
    looks = sorted(set([x for x in cfg["판정_시점"] if x < need] + [need]))
    rows = []
    for ad in ads:
        b = by[(ad, "*")]; n = len(b["들어옴"]); k = len(b["첫수"] & b["들어옴"])
        chans = {ch: {"들어옴": len(v["들어옴"]), "첫수": len(v["첫수"] & v["들어옴"])} for (a, ch), v in by.items() if a == ad and ch != "*"}
        secs = sorted(x for x in b["초"] if x is not None)
        rr = (b["다시"], b["끝"])
        rows.append({"광고": ad, "들어옴": n, "첫수": k, "주_지표": r(k / n) if n else None, "구간": [r(v) for v in wilson(k, n)],
                     "다시_하기": rr, "다시_하기_비율": r(rr[0] / rr[1]) if rr[1] else None,
                     "다시_하기_구간": [r(v) for v in wilson(*rr)], "첫_수까지_초": secs[len(secs) // 2] if secs else None,
                     "채널별": chans, "시점": max([x for x in looks if n >= x], default=None)})
    days = days if days is not None else len({d for v in by.values() for d in v["날"] if d})
    tot_n = sum(x["들어옴"] for x in rows); tot_k = sum(x["첫수"] for x in rows)
    tot_rr = (sum(x["다시_하기"][0] for x in rows), sum(x["다시_하기"][1] for x in rows))
    mean_rr = tot_rr[0] / tot_rr[1] if tot_rr[1] else None
    # 시점에 닿은 광고만 「광고 하나 대 나머지 합산」으로 비교, 홈 보정, 시점 기준
    cand = [x for x in rows if x["시점"] is not None]
    ps = [two_prop_p(x["첫수"], x["들어옴"], tot_k - x["첫수"], tot_n - x["들어옴"]) for x in cand]
    sig = holm([p if p is not None else 1.0 for p in ps], cfg["시점_기준"]) if cand else []
    for x, p, s in zip(cand, ps, sig):
        rest = (tot_k - x["첫수"]) / (tot_n - x["들어옴"]) if tot_n - x["들어옴"] else None
        x["나머지_대비"] = {"나머지": r(rest), "p": r(p, 4), "보정_후_차이": s}
    for x in rows:
        c = x.get("나머지_대비")
        if x["들어옴"] < cfg["방향_최소"]:
            x["판정"] = "보류"; x["이유"] = f"들어온 사람 {x['들어옴']}명, {cfg['방향_최소']}명부터 방향을 적음"
        elif c and c["보정_후_차이"]:
            up = x["주_지표"] > c["나머지"]
            safe_bad = up and mean_rr is not None and x["다시_하기_구간"][1] is not None and x["다시_하기_구간"][1] < mean_rr
            if not up:
                x["판정"] = "확정"; x["이유"] = "나머지보다 낮음"
            elif safe_bad:
                x["판정"] = "방향"; x["이유"] = "앞서지만 다시 하기 비율이 평균보다 낮아 확정 보류"
            elif days < cfg["최소_날_수"]:
                x["판정"] = "방향"; x["이유"] = f"앞서지만 기록 {days}일, {cfg['최소_날_수']}일 채운 뒤 확정"
            else:
                x["판정"] = "확정"; x["이유"] = "나머지보다 높음"
        elif x["들어옴"] >= need:
            x["판정"] = "결론 없음"; x["이유"] = f"필요 표본 {need}명을 채웠지만 차이가 없어 이 비교는 닫음"
        else:
            nxt = min((v for v in looks if v > x["들어옴"]), default=need)
            x["판정"] = "방향"; x["이유"] = f"다음 판정은 {nxt}명에서"
    best = p_best(rows)
    for x in rows: x["최고일_확률"] = best.get(x["광고"])
    return {"규칙": {k: cfg[k] for k in ("판", "주_지표", "보조_지표", "안전_지표", "기준값", "최소_감지_차이", "유의수준", "검정력",
                                       "시점_기준", "방향_최소", "최소_날_수", "피로")},
            "판정_시점": looks, "필요_표본": need, "광고": rows, "기록_날_수": days,
            "전체": {"들어옴": tot_n, "첫수": tot_k, "다시_하기_평균": r(mean_rr)}}


def build(requests, events_dir=("runs", "events")):
    ev = perf.load_events(paths.p(*events_dir))
    cfg = plan(); out = evaluate(ev, requests, cfg)
    out["피로"] = fatigue(ev, ad_of(requests), cfg)
    return out
