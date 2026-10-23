"""공개용 묶음 시험: 꼴, 넣지 말 것, 게시 막힌 게임 빠짐, 숫자가 원래 기록과 같은지."""
import os, sys, json, tempfile, shutil, glob
ENG = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ROOT = os.path.dirname(ENG)
sys.path.insert(0, ENG)
from adf import export
tmp = tempfile.mkdtemp()
shutil.copy(os.path.join(ROOT, "board", "notes.json"), tmp)
export.build(tmp)
d = json.load(open(os.path.join(tmp, "data.json"), encoding="utf-8"))
s = open(os.path.join(tmp, "data.json"), encoding="utf-8").read()
assert d["판"] == "adf-board/1"
for bad in ("처리자", "누가", "EXPORT_KEY", "TOKEN", "gem-tower", "보석타워"):
    assert bad not in s, bad                                                   # 사람 이름·열쇠·게시 막힌 게임은 빠짐
assert all(g["게시_가능"] for g in d["게임"])
for r in d["심사_이력"]:                                                       # 화면 숫자 = score.json 숫자
    sc = os.path.join(ROOT, "judge", "runs", r["회차"], "score.json")
    if os.path.exists(sc): assert json.load(open(sc, encoding="utf-8"))["판정_일치"] == r["판정_일치"], r["회차"]
ids = [i["id"] for g in d["생성분"] for i in g["소재"]]
assert len(ids) == len(set(ids))
assert open(os.path.join(tmp, "data.js"), encoding="utf-8").read().startswith("window.ADF_BOARD = ")
for a in d["광고"]:                                                            # 광고 → 대본·심사로 따라갈 수 있음, 게시 주소는 빠짐
    assert "소재" in a and "심사_회차" in a and "공개" in a, a["id"]
assert "youtube.com/shorts" not in s
shutil.rmtree(tmp); print("통과")
