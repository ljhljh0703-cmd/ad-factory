"""사실표 자동 대조 시험: 지금까지 사람이 고친 사실표 판(2~7)을 하나씩 되돌려, 자동 대조가 그 빈틈을 잡는지 본다.
판 2는 뜻을 읽어야 하는 수정(방벽 없음, 끝나는 경우 설명)이라 자동으로 못 잡는 것으로 기록한다."""
import json, os, copy, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from adf import factcheck, paths

AD = paths.p("adapters", "jelly-panic"); FACTS = paths.p("game", "jelly-panic.json")
BASE = json.load(open(FACTS, encoding="utf-8"))


def run(f):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as t:
        json.dump(f, t, ensure_ascii=False)
    r, _ = factcheck.compare(AD, t.name); os.unlink(t.name); return r


def revert(n):
    f = copy.deepcopy(BASE)
    if n == 2:
        f["없는_것"] = [x for x in f["없는_것"] if x != "방벽"]; f.pop("판이_끝나는_경우")
    if n == 3:
        f["없는_것"] = [x for x in f["없는_것"] if not x.startswith("화면 위쪽 사진 칸")]
        f["지키는것"][0]["다시_나옴"] = "아기를 구출하면 다시 나옴"
    if n == 4:
        f["화면"] = [x for x in f["화면"] if "판 번호" not in x]
        f["같은_판"] = "주소 끝에 ?seed=번호 를 붙이면 그 판이 열림. 판 번호는 화면에 보이지 않음"
    if n == 5:
        f.pop("판_끝_문구"); f["안내_문구"]["설명"] = "위협이 나오면 안내가 뜸"
    if n == 6:
        f["화면"] = [x for x in f["화면"] if "상태 줄" not in x]; f["안내_문구"]["목록"] = f["안내_문구"]["목록"][:5]
    if n == 7:
        f["안내_문구"]["목록"] = f["안내_문구"]["목록"][:12]
        f["판_끝_문구"] = {k: v for k, v in f["판_끝_문구"].items() if k != "스테이지 목표를 이룸"}
        f["판_끝_문구"]["스테이지 수를 다 씀"] = "수를 다 썼어요, 다시 도전해요"
    return f


def main():
    rows = []
    base = run(BASE); assert base["결론"] == "통과", base["어긋남"]
    for n in (2, 3, 4, 5, 6, 7):
        r = run(revert(n))
        rows.append({"판": n, "잡음": r["결론"] == "막음", "어긋남": [i["종류"] for i in r["어긋남"]]})
    for r in rows: print(json.dumps(r, ensure_ascii=False))
    caught = [r["판"] for r in rows if r["잡음"]]
    print("잡은 판:", caught, f"{len(caught)}/{len(rows)}")
    assert caught == [3, 4, 5, 6, 7], caught
    return rows


if __name__ == "__main__":
    main()
