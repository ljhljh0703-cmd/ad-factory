"""녹화본 대조 검사: 대본의 컷이 실제 녹화 화면에 그대로 있는지 맞춰 본다.

심사기는 대본 글만 본다. 안내 문구가 뜨는 순간, 화면 배치처럼 화면에서만 확인되는 것은
녹화본을 1초마다 잘라 모은 판(접촉 시트)과 대본을 나란히 놓고 이미지를 읽는 모델이 컷마다 판정한다.

  python3 footage_check.py sheets --video 녹화.webm --out runs/F01          # 1초 프레임 → 시트 PNG
  python3 footage_check.py prompt --script 대본.json --out runs/F01         # 판정 요청문(prompt.md)
  python3 footage_check.py report --out runs/F01                            # 모델 답(answer.jsonl) → 요약
"""
import argparse, glob, json, os, subprocess
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
PER = 8  # 시트 한 장에 프레임 수 (4 x 2)

def sheets(video, out, fps=1):
    fr = os.path.join(out, "frames"); os.makedirs(fr, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vf", f"fps={fps}", os.path.join(fr, "%04d.png")], check=True)
    fs = sorted(glob.glob(os.path.join(fr, "*.png")))
    font = ImageFont.truetype(FONT, 26)
    w0, h0 = Image.open(fs[0]).size; W, H = w0, h0  # 아래쪽(판 번호 줄)까지 다 보이게. 처음엔 86%로 잘라 판 번호가 빠졌음
    paths = []
    for s in range(0, len(fs), PER):
        sheet = Image.new("RGB", (W * 4, H * 2), "white")
        for k, f in enumerate(fs[s:s + PER]):
            sec = round((int(os.path.basename(f)[:-4]) - 1) / fps, 1)
            im = Image.open(f).convert("RGB").crop((0, 0, W, H)); d = ImageDraw.Draw(im)
            d.rectangle((0, H - 44, 96, H), fill="black"); d.text((8, H - 42), f"{sec}s", fill="white", font=font)
            sheet.paste(im, ((k % 4) * W, (k // 4) * H))
        p = os.path.join(out, f"sheet_{s // PER + 1:02d}.png"); sheet.save(p); paths.append(p)
    json.dump({"video": video, "fps": fps, "frames": len(fs), "sheets": paths}, open(os.path.join(out, "sheets.json"), "w"), ensure_ascii=False, indent=1)
    print(len(fs), "frames →", len(paths), "sheets")

def prompt(script, out, final=False):
    meta = json.load(open(os.path.join(out, "sheets.json")))
    c = json.load(open(script))
    cuts = [k["장면"] if isinstance(k, dict) else k for k in c.get("컷", [])]
    p = f"""너는 광고 대본과 실제 녹화 화면을 맞춰 보는 검수자다. 대본에 적힌 장면이 녹화 화면에 그대로 있는지만 본다.
화면은 아래 시트 이미지들이다. 녹화본을 1초마다 자른 프레임이 시트 한 장에 {PER}개씩, 왼쪽 아래에 몇 초 화면인지 적혀 있다.
시트: {", ".join(meta["sheets"])}

## 대본 ({c.get("id")}, {c.get("유형")})
컷 0(첫 컷): {c.get("첫컷","")}
""" + "\n".join(f"컷 {i+1}: {t}" for i, t in enumerate(cuts)) + f"""
자막(편집으로 얹는 글, 화면 판정에서 제외): {" / ".join(c.get("자막") or [])}

## 판정하는 법
""" + ("""- 이 영상은 편집이 끝난 광고 완성본이다. 위쪽 자막 상자, 끝 화면 글자, 그림책 그림 구간은 편집으로 넣은 것이라 판정하지 않는다. 게임 화면 부분이 대본의 컷과 같은지만 본다. 그림책 그림 컷은 「편집」으로 판정하고, 그림에 대본에 없는 장면(까마귀가 아기에 닿거나 물고 감 등)이 있으면 「다름」으로 적는다.
""" if final else "") + f"""- 컷마다 녹화 화면에서 그 장면에 해당하는 초를 찾는다.
- 컷에 적힌 화면 요소(보드 위 블록·위협 아이콘·카운트다운·게임이 띄우는 문구·판 끝 화면 문구·버튼 위치)가 그 프레임에 실제로 보이면 「맞음」.
- 장면은 있는데 적힌 요소 일부가 다르거나 없으면 「다름」. 무엇이 다른지 화면에 실제로 보이는 것을 그대로 적는다(문구는 보이는 글자 그대로).
- 녹화 어디에도 그 장면이 없으면 「없음」.
- 되감기·멈춤·확대·느리게처럼 편집으로 만드는 동작은 원본 녹화에 없다. 이런 컷은 「편집」으로 판정하고, 편집에 쓰는 장면(되감아 돌아가는 화면 등)이 녹화에 있는지만 「화면에_보이는_것」에 적는다.
- 컷에 적힌 게임 속 문구는 글자 하나까지 대조한다. 편집 자막은 판정하지 않는다.

## 출력
컷 하나에 한 줄, JSON Lines만. 설명 없이.
{{"컷": 1, "판정": "맞음|다름|없음|편집", "초": [52, 53], "화면에_보이는_것": "...", "다른_점": ""}}
"""
    open(os.path.join(out, "prompt.md"), "w").write(p); print(os.path.join(out, "prompt.md"))

def report(out):
    rows = [json.loads(l) for l in open(os.path.join(out, "answer.jsonl")) if l.strip()]
    bad = [r for r in rows if r["판정"] in ("다름", "없음")]
    res = {"컷_수": len(rows), "맞음": sum(r["판정"] == "맞음" for r in rows), "편집": sum(r["판정"] == "편집" for r in rows), "다름": sum(r["판정"] == "다름" for r in rows),
           "없음": sum(r["판정"] == "없음" for r in rows), "결론": "통과" if not bad else "사람 확인", "걸린_컷": bad}
    json.dump(res, open(os.path.join(out, "report.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "걸린_컷"}, ensure_ascii=False))

if __name__ == "__main__":
    a = argparse.ArgumentParser(); a.add_argument("cmd"); a.add_argument("--video"); a.add_argument("--script"); a.add_argument("--out", required=True); a.add_argument("--fps", type=float, default=1); a.add_argument("--final", action="store_true")
    x = a.parse_args(); os.makedirs(x.out, exist_ok=True)
    {"sheets": lambda: sheets(x.video, x.out, x.fps), "prompt": lambda: prompt(x.script, x.out, x.final), "report": lambda: report(x.out)}[x.cmd]()
