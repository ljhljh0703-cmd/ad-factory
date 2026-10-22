"""성과 보고: 게임의 익명 기록(수집기 JSONL)과 플랫폼 통계(CSV, 있으면)를 광고별로 묶는다.

표본이 작으면(시작 30판 미만) 수치를 보여 주되 결론을 내리지 않는다.
소재 피로: 광고별 하루 지표(클릭률, 없으면 하루 시작 판 수)가 최근 3일 평균이 최고 3일 평균의 70% 아래로
내려가고 그 기간 노출이 줄지 않았으면 「피로 의심」.
"""
import json, os, glob, csv, collections, statistics, datetime

MIN_N = 30


def load_events(d):
    rows = []
    for f in sorted(glob.glob(os.path.join(d, "*.jsonl"))):
        day = os.path.basename(f)[:10]
        for l in open(f, encoding="utf-8"):
            if l.strip():
                e = json.loads(l)
                if e.get("src") == "test": continue  # 배포 확인용 시험 기록
                e["day"] = day; rows.append(e)
    return rows


def load_platform(path):
    if not path or not os.path.exists(path): return []
    out = []
    for r in csv.DictReader(open(path, encoding="utf-8")):
        out.append({"day": r["날짜"], "ad": r["ad"], "채널": r.get("채널", ""), "노출": int(r.get("노출") or 0),
                    "조회": int(r.get("조회") or 0), "클릭": int(r.get("링크클릭") or 0)})
    return out


def by_ad(events):
    g = collections.defaultdict(list)
    for e in events: g[e.get("ad") or "(광고 없음)"].append(e)
    out = {}
    for ad, es in g.items():
        starts = [e for e in es if e["type"] == "start"]
        sessions = {e["sid"] for e in es}
        first = [e for e in es if e["type"] == "first_move"]
        ends = [e for e in es if e["type"] == "end"]
        rs = [e for e in es if e["type"] == "restart"]
        land = {e["sid"] for e in starts if e.get("n") == 0}
        out[ad] = {
            "채널": sorted({e.get("src") for e in es}),
            "들어온_사람(탭)": len(sessions),
            "시작한_판": len(starts),
            "첫_수_둔_비율": round(len({e['sid'] for e in first}) / len(land), 3) if land else None,
            "첫_수까지_초(중앙값)": statistics.median([e["after"] for e in first]) if first else None,
            "끝난_판": len(ends),
            "다시_하기_비율": round(len(rs) / len(ends), 3) if ends else None,
            "놓은_수(중앙값)": statistics.median([e["placements"] for e in ends]) if ends else None,
            "끝난_이유": dict(collections.Counter(e.get("cause") for e in ends)),
            "표본": "충분" if len(starts) >= MIN_N else f"작음(시작 {len(starts)}판, {MIN_N}판 미만은 결론 없음)",
        }
    return out


def fatigue(platform, events):
    """광고별 하루 지표로 피로 의심을 찾는다."""
    series = collections.defaultdict(dict)
    if platform:
        for r in platform:
            s = series[r["ad"]].setdefault(r["day"], {"노출": 0, "클릭": 0}); s["노출"] += r["노출"]; s["클릭"] += r["클릭"]
        metric = lambda s: s["클릭"] / s["노출"] if s["노출"] else 0
        name = "클릭률"
    else:
        for e in events:
            if e["type"] == "start":
                s = series[e.get("ad") or "(광고 없음)"].setdefault(e["day"], {"노출": None, "시작": 0}); s["시작"] += 1
        metric = lambda s: s["시작"]
        name = "하루 시작 판"
    out = {}
    for ad, days in series.items():
        ds = sorted(days); vals = [metric(days[d]) for d in ds]
        if len(vals) < 6:
            out[ad] = {"지표": name, "판단": f"날 수 부족({len(vals)}일, 6일부터 봄)"}; continue
        roll = [sum(vals[i:i + 3]) / 3 for i in range(len(vals) - 2)]
        peak, last = max(roll), roll[-1]
        imp_ok = True
        if platform:
            imp = [days[d]["노출"] for d in ds]
            imp_ok = sum(imp[-3:]) >= 0.8 * max(sum(imp[i:i + 3]) for i in range(len(imp) - 2))
        tired = peak > 0 and last < 0.7 * peak and imp_ok
        out[ad] = {"지표": name, "최고_3일": round(peak, 4), "최근_3일": round(last, 4), "비율": round(last / peak, 3) if peak else None,
                   "판단": "피로 의심: 새 소재로 바꾸거나 첫 3초를 바꿔 볼 때" if tired else "괜찮음"}
    return out


def report_prompt(table, fat, period, note):
    return f"""너는 게임 광고 운영 담당자다. 아래 숫자만 보고 이번 주 광고 성과 보고를 쓴다.

## 규칙
- 숫자에 없는 것을 지어내지 않는다. 표본이 「작음」인 광고는 숫자만 옮기고 좋다·나쁘다 판단을 하지 않는다.
- 형식은 세 덩어리: 문제 / 해결 / 다음. 각 덩어리는 3줄 이내.
- 광고 이름(ad)과 채널을 그대로 쓴다. 과장·감탄 표현 없이 쓴다.
- 피로 판단이 「피로 의심」인 광고만 바꿀 것을 권한다.

## 기간
{period}
{note}

## 광고별 게임 안 기록
{json.dumps(table, ensure_ascii=False, indent=1)}

## 소재 피로
{json.dumps(fat, ensure_ascii=False, indent=1)}
"""


COLLECTOR = "https://jelly-panic-collector.vercel.app/api/export"


def pull(out_dir, days, key=None):
    """수집기에서 날짜별 기록을 내려받아 out_dir/YYYY-MM-DD.jsonl 로 둔다(같은 날은 덮어씀). 열쇠는 ADF_EXPORT_KEY."""
    import urllib.request
    key = key or os.environ.get("ADF_EXPORT_KEY")
    if not key: raise RuntimeError("ADF_EXPORT_KEY 없음: Vercel 프로젝트 jelly-panic-collector 의 EXPORT_KEY 값")
    os.makedirs(out_dir, exist_ok=True); got = {}
    for d in days:
        req = urllib.request.Request(f"{COLLECTOR}?day={d}", headers={"x-export-key": key})
        txt = urllib.request.urlopen(req, timeout=60).read().decode("utf-8")
        open(os.path.join(out_dir, f"{d}.jsonl"), "w", encoding="utf-8").write(txt)
        got[d] = sum(1 for l in txt.splitlines() if l.strip())
    return got
