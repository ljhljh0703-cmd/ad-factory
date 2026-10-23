"""심사 품질 계산 시험. 아래 숫자는 시험용으로 만든 값이며 실제 심사 결과가 아니다."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from adf import quality, stats

# 윌슨 구간: 알려진 값(10건 중 0건 → 위쪽 약 0.278), 0건 위쪽 한계(30건 → 약 0.095, 3/30 = 0.1 근처)
lo, hi = stats.wilson(0, 10)
assert abs(lo) < 1e-9 and abs(hi - 0.2775) < 0.001, (lo, hi)
assert abs(stats.upper_zero(30) - 0.0950) < 0.001
# 표본 계산: 기준 50%에서 10%p 차이, 유의수준 5%, 검정력 80% → 한 쪽 약 385~390
n = stats.n_per_arm(0.5, 0.10)
assert 380 <= n <= 395, n
assert stats.n_per_arm(0.5, 0.10, k=3) > n                   # 비교가 많으면 더 많이 필요
assert stats.holm([0.001, 0.04, 0.03]) == [True, False, False]

cfg = quality.config()
score = {"혼동표(정답→판정)": {"통과": {"통과": 8, "반려": 1, "사람 확인": 1},
                              "반려": {"통과": 1, "반려": 9, "사람 확인": 0},
                              "사람 확인": {"통과": 0, "반려": 0, "사람 확인": 0}}}
g = quality.gold_quality({"run": "T", "set": "dev"}, score, cfg)
assert g["소재_수"] == 20 and g["반려_정답"] == 10 and g["반려_잡음"] == 9
want = 1 * cfg["비용"]["통과→반려"] + 1 * cfg["비용"]["통과→사람 확인"] + 1 * cfg["비용"]["반려→통과"]
assert abs(g["비용_합"] - want) < 1e-9, g
assert g["반려_정밀도"] == 0.9 and g["informedness"] == 0.8, g      # 반려 9/10 · 재현율 0.9 + 특이도 0.9 - 1
assert g["반려_정답_필요"] == 59
c = quality.rule_candidates([{"id": "Q1", "소재": "a", "상태": "처리", "뒤집음": True, "AI_판정": "통과", "결정": "반려"},
                             {"id": "Q2", "소재": "b", "상태": "처리", "뒤집음": False}, {"id": "Q3", "소재": "c", "상태": "대기", "뒤집음": True}])
assert [x["검토"] for x in c] == ["Q1"]

n2, diff = quality.flips([{"id": "a", "AI_판정": ["통과", "통과"]}, {"id": "b", "AI_판정": ["통과", "반려"]},
                          {"id": "c", "경로": "① 규칙"}])
assert n2 == 2 and diff == ["b"]

items = [{"id": f"X-{i}", "최종": "통과", "사람": None} for i in range(10)] + [{"id": "X-h", "최종": "통과", "사람": {"판정": "반려"}}]
p1 = quality.audit_plan("X", items, cfg); p2 = quality.audit_plan("X", list(reversed(items)), cfg)
assert p1 == p2, "고르는 순서가 입력 순서에 따라 바뀌면 안 됨"
assert p1["목표"] == 3 and len(p1["더_볼_것"]) == 2               # 11개 × 20% → 3개, 이미 1개 봄
e = quality.audit_estimate(items, cfg["신뢰수준"])
assert e["본_수"] == 1 and e["사람_반려"] == 1
print("통과")
