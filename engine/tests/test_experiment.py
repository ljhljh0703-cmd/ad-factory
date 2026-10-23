"""소재 실험 판정 시험. 아래 기록은 시험용으로 만든 값이며 실제 성과가 아니다."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from adf import experiment

req = [{"광고": "A1", "소재": "R1"}, {"광고": "A2", "소재": "R2"}, {"광고": "A3", "소재": "R3"}]

def sessions(ad, n, p, src="reels", day="2026-11-01", tag=""):
    out = []; k = round(n * p)                      # 정확히 k명이 첫 수를 둔다(우연 없이)
    for i in range(n):
        sid = f"{ad}{tag}-{i}"; out.append({"sid": sid, "n": 0, "type": "start", "ad": ad, "src": src, "day": day})
        if i < k: out.append({"sid": sid, "n": 1, "type": "first_move", "ad": ad, "src": src, "after": 2, "day": day})
    return out

cfg = experiment.plan()
v = lambda res: {x["광고"]: x["판정"] for x in res["광고"]}
# 30명 미만은 보류, 꼬리표가 소재 id(R1)든 광고 이름(A2)이든 광고 단위로 묶이고 시험 기록은 빠짐
s = experiment.evaluate(sessions("R1", 20, .8) + sessions("A2", 20, .3) + sessions("deploycheck", 50, .9), req, cfg, days=10)
assert v(s) == {"A1": "보류", "A2": "보류"}, v(s)
# 30명 이상이어도 첫 판정 시점(60명) 전이면 방향
s = experiment.evaluate(sessions("R1", 40, .8) + sessions("R2", 40, .3), req, cfg, days=10)
assert v(s) == {"A1": "방향", "A2": "방향"}, v(s)
need = experiment.evaluate(sessions("R1", 1, .5) + sessions("R2", 1, .5) + sessions("R3", 1, .5), req, cfg)["필요_표본"]
big = sessions("R1", need, .75) + sessions("R2", need, .45) + sessions("R3", need, .72)
s = experiment.evaluate(big, req, cfg, days=10)
assert v(s)["A2"] == "확정" and "낮음" in [x for x in s["광고"] if x["광고"] == "A2"][0]["이유"], s["광고"]
# 날 수가 모자라면 앞서도 방향
assert experiment.evaluate(big, req, cfg, days=3)["광고"][0]["판정"] == "방향"
# 최고일 확률은 합이 1 근처, 가장 높은 광고가 가장 큼
pb = {x["광고"]: x["최고일_확률"] for x in s["광고"]}
assert abs(sum(pb.values()) - 1) < 0.01 and pb["A1"] > pb["A2"], pb
# 차이가 작으면 필요 표본을 채워도 결론 없음
s = experiment.evaluate(sessions("R1", need, .60) + sessions("R2", need, .58), req, cfg, days=10)
assert set(v(s).values()) == {"결론 없음"}, v(s)
# 피로: 유입만 줄면 「신호 하나」, 유입과 첫 수 비율이 같이 떨어지면 피로
ev = []
for d in range(14):
    day = f"2026-11-{d+1:02d}"
    ev += sessions("R1", 40 if d < 7 else 10, .7, day=day, tag=day)              # 유입만 줄어듦
    ev += sessions("R2", 40 if d < 7 else 10, .7 if d < 7 else .4, day=day, tag=day)  # 둘 다 떨어짐
f = experiment.fatigue(ev, experiment.ad_of(req), cfg)
assert f["A1"]["판단"].startswith("신호 하나") and f["A2"]["판단"].startswith("피로"), f
print("통과")
