"""소재 피로 감지 시험. 아래 숫자는 시험용으로 만든 값이며 실제 성과가 아니다."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from adf import perf

def plat(ad, ctr, imp=1000):
    return [{"day": f"2026-11-{i+1:02d}", "ad": ad, "채널": "tiktok", "노출": imp, "조회": imp, "클릭": int(imp * c)} for i, c in enumerate(ctr)]

rows = plat("지침", [.05, .052, .05, .045, .03, .028, .027]) + plat("고름", [.04, .041, .039, .04, .042, .04, .041]) + plat("짧음", [.05, .01])
rows += [{"day": "2026-11-07", "ad": "노출감소", "채널": "x", "노출": 0, "조회": 0, "클릭": 0}]
f = perf.fatigue(rows, [])
print(f)
assert f["지침"]["판단"].startswith("피로"), f["지침"]
assert f["고름"]["판단"] == "괜찮음"
assert f["짧음"]["판단"].startswith("날 수 부족")
# 노출이 줄어서 클릭률이 떨어진 경우는 피로로 보지 않음
r2 = [dict(r) for r in plat("노출줄음", [.05, .05, .05, .05, .03, .03, .03])]
for r in r2[-3:]: r["노출"] = 300
assert not perf.fatigue(r2, [])["노출줄음"]["판단"].startswith("피로")
print("통과")
