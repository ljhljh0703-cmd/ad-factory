# 평가셋 점검: 형식 · 규칙별 개수 · 통과 소재가 기계 조건을 지키는지. holdout 은 개수만 센다.
import json, re, sys, collections
RULES=[f"R{i}" for i in range(1,12)]+[f"G{i}" for i in range(2,9)]
def load(p): return [json.loads(l) for l in open(p,encoding="utf-8")]
dev, hold = load("dev.jsonl"), load("holdout/holdout.jsonl")
fail=[]
for i in dev+hold:
    if i["정답"] not in ("통과","반려","사람 확인"): fail.append(f'{i["id"]} 정답 값')
    if i["정답"]!="통과" and not i["걸린것"]: fail.append(f'{i["id"]} 걸린것 비어 있음')
    if i["정답"]=="통과" and i["걸린것"]: fail.append(f'{i["id"]} 통과인데 걸린것 있음')
# 통과 소재가 기계로 볼 수 있는 조건을 지키는지 (dev 만)
for i in dev:
    if i["정답"]!="통과" or i["종류"]!="영상": continue
    if i["화면비"]!="9:16": fail.append(f'{i["id"]} G6')
    if not i["게임이름_처음_나오는_초"] or i["게임이름_처음_나오는_초"]>5: fail.append(f'{i["id"]} G3')
    if not i["자막"]: fail.append(f'{i["id"]} G4')
    if not i["링크"] or "?src=" not in i["링크"] or not i["끝"]: fail.append(f'{i["id"]} G5')
    if re.search(r"\d"," ".join(i["자막"]+[i["끝"]])): fail.append(f'{i["id"]} G8 숫자')
cnt={k:collections.Counter() for k in ("dev","holdout")}
for name,rows in (("dev",dev),("holdout",hold)):
    for i in rows:
        for r in i["걸린것"]: cnt[name][r]+=1
for r in RULES:
    tot=cnt["dev"][r]+cnt["holdout"][r]
    if tot<2 and r.startswith("R"): fail.append(f"{r} 반려 소재 {tot}개 (2개 이상 필요)")
    if r.startswith("R") and cnt["dev"][r]<1: fail.append(f"{r} dev 에 없음")
lab=lambda rows: collections.Counter(i["정답"] for i in rows)
print("dev", len(dev), dict(lab(dev)), "경계", sum(i["경계"] for i in dev))
print("holdout", len(hold), dict(lab(hold)), "경계", sum(i["경계"] for i in hold))
print("규칙별(dev+holdout):", " ".join(f"{r}={cnt['dev'][r]+cnt['holdout'][r]}" for r in RULES))
print("결과:", "통과" if not fail else "실패 "+str(len(fail)))
for f in fail: print("  -",f)
sys.exit(1 if fail else 0)
