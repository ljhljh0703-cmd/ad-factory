"""AI 광고 편집기: 기록한 실제 플레이 프레임 + 게임 소리 기록 + 그림책 그림 + 자막으로 9:16 영상을 만든다.
사람 손 편집 없이 편집 결정표(JSON)만으로 다시 만들 수 있다.

  python3 render.py ad.json out.mp4
"""
import json, os, sys, subprocess, wave, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS, SR = 1080, 1920, 30, 44100
HERE = os.path.dirname(os.path.abspath(__file__))
FONT_B = "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc"
FONT_M = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
BROWN = (74, 46, 23); PINK = (232, 80, 126)

def bg():
    top, bot = np.array([253, 242, 228]), np.array([244, 232, 246])
    g = np.linspace(0, 1, H)[:, None, None]
    return Image.fromarray((top * (1 - g) + bot * g).repeat(W, 1).astype(np.uint8))
BG = bg()

class Rec:
    def __init__(self, name):
        self.dir = os.path.join(HERE, name); self.log = json.load(open(os.path.join(self.dir, "log.json")))
        self.fr = self.log["frames"]
    def img(self, n):
        im = Image.open(os.path.join(self.dir, "frames", f"{n:05d}.jpg")).convert("RGB")
        return im.crop(tuple(self.log.get("crop") or (0, 0, 1080, 1760)))  # 기본: 젤리 패닉 점수판부터 판 번호까지. 어댑터마다 log.json 의 crop
    def t(self, n): return self.fr[n]["wall"] / 1000.0

GAME_BOX = (110, 370, 860)  # x, y, width
def place_game(canvas, im):
    w = GAME_BOX[2]; h = int(im.height * w / im.width)
    g = im.resize((w, h), Image.LANCZOS)
    mask = Image.new("L", (w, h), 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), 36, fill=255)
    sh = Image.new("RGBA", (w + 60, h + 60), (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle((30, 40, w + 30, h + 40), 40, fill=(120, 80, 60, 70))
    canvas.paste(sh.filter(ImageFilter.GaussianBlur(18)), (GAME_BOX[0] - 30, GAME_BOX[1] - 30), sh.filter(ImageFilter.GaussianBlur(18)))
    canvas.paste(g, (GAME_BOX[0], GAME_BOX[1]), mask)

def caption(canvas, text, y=150, size=66, color=BROWN, fill=(255, 255, 255, 235)):
    d = ImageDraw.Draw(canvas); f = ImageFont.truetype(FONT_B, size)
    lines = text.split("\n"); hs = [d.textbbox((0, 0), l, font=f) for l in lines]
    tw = max(b[2] - b[0] for b in hs); lh = size + 16; th = lh * len(lines)
    box = Image.new("RGBA", (tw + 80, th + 44), (0, 0, 0, 0)); ImageDraw.Draw(box).rounded_rectangle((0, 0, tw + 80, th + 44), 34, fill=fill)
    x0 = (W - tw - 80) // 2; canvas.paste(box, (x0, y), box)
    for k, l in enumerate(lines):
        b = d.textbbox((0, 0), l, font=f); d.text(((W - (b[2] - b[0])) // 2, y + 16 + k * lh), l, font=f, fill=color)

def label(canvas, text, xy, size=40, color=(255, 255, 255), fill=(74, 46, 23, 220)):
    d = ImageDraw.Draw(canvas); f = ImageFont.truetype(FONT_M, size); b = d.textbbox((0, 0), text, font=f)
    box = Image.new("RGBA", (b[2] - b[0] + 44, b[3] - b[1] + 30), (0, 0, 0, 0)); ImageDraw.Draw(box).rounded_rectangle((0, 0, box.width, box.height), 22, fill=fill)
    canvas.paste(box, xy, box); d.text((xy[0] + 22, xy[1] + 8), text, font=f, fill=color)

def storybook(path, k, n, zoom=0.06):
    im = Image.open(path).convert("RGB"); s = max(W / im.width, H / im.height) * (1 + zoom * k / max(n - 1, 1))
    im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
    x, y = (im.width - W) // 2, (im.height - H) // 2; return im.crop((x, y, x + W, y + H))


def ring(canvas, rec, cells, text="여기!"):
    """편집 표시: 보드 칸을 동그라미(둥근 사각) 표시. 화면 내용은 바꾸지 않는다."""
    b = rec.log["board"]; sc = rec.log.get("scale", 2.769); CSs = (b["width"] - 20) / 8
    k = GAME_BOX[2] / 1080.0
    xs = [b["x"] + 10 + c * CSs for r, c in cells]; ys = [b["y"] + 10 + r * CSs for r, c in cells]
    x0, y0 = min(xs), min(ys); x1, y1 = max(xs) + CSs, max(ys) + CSs
    cy = (rec.log.get("crop") or (0, 0))[1]
    X0, Y0 = GAME_BOX[0] + x0 * sc * k - 8, GAME_BOX[1] + (y0 * sc - cy) * k - 8; X1, Y1 = GAME_BOX[0] + x1 * sc * k + 8, GAME_BOX[1] + (y1 * sc - cy) * k + 8
    d = ImageDraw.Draw(canvas); d.rounded_rectangle((X0, Y0, X1, Y1), 18, outline=PINK, width=10)
    if text:
        f = ImageFont.truetype(FONT_B, 44); tb = d.textbbox((0, 0), text, font=f); tw = tb[2] - tb[0]
        tx = min(max(X0 + (X1 - X0 - tw) / 2, 30), W - tw - 30); ty = Y0 - 70 if Y0 > 450 else Y1 + 14
        d.rounded_rectangle((tx - 16, ty - 6, tx + tw + 16, ty + 58), 20, fill=PINK); d.text((tx, ty), text, font=f, fill=(255, 255, 255))

# ── 소리: 게임이 낸 음을 같은 값으로 합성 ──
def osc(kind, ph):
    if kind == "square": return np.sign(np.sin(ph))
    if kind == "triangle": return 2 / math.pi * np.arcsin(np.sin(ph))
    if kind == "sawtooth": return 2 * ((ph / (2 * math.pi)) % 1) - 1
    return np.sin(ph)
def tone(buf, at, a):
    n = int(max(a["dur"], 0.02) * SR); t = np.arange(n) / SR; d = max(a["dur"], 0.02)
    f = a["freq"] * (a["slide"] / a["freq"]) ** (t / d) if a.get("slide") else np.full(n, a["freq"])
    ph = 2 * math.pi * np.cumsum(f) / SR; g = a["vol"] * (0.001 / a["vol"]) ** (t / d)
    i = int(at * SR)
    if i < 0 or i >= len(buf): return
    m = min(n, len(buf) - i); buf[i:i + m] += (osc(a["type"], ph) * g)[:m]
def page_sound(buf, at):
    n = int(0.45 * SR); t = np.arange(n) / SR; rng = np.random.default_rng(1)
    s = rng.standard_normal(n) * np.sin(math.pi * t / 0.45) ** 2 * 0.05
    s = np.convolve(s, np.ones(30) / 30, "same"); i = int(at * SR); buf[i:i + n] += s[:max(0, len(buf) - i)]

def ring_box(canvas, rec, box, text=""):
    """편집 표시: 화면 좌표(CSS px) 상자에 테두리. 판 칸이 없는 게임(보석타워 등)에 쓴다."""
    sc = rec.log.get("scale", 2.769); cx, cy = (rec.log.get("crop") or (0, 0))[:2]
    k = GAME_BOX[2] / ((rec.log.get("crop") or (0, 0, 1080))[2] - cx)
    x, y, w, h = box
    X0, Y0 = GAME_BOX[0] + (x * sc - cx) * k - 8, GAME_BOX[1] + (y * sc - cy) * k - 8
    X1, Y1 = GAME_BOX[0] + ((x + w) * sc - cx) * k + 8, GAME_BOX[1] + ((y + h) * sc - cy) * k + 8
    d = ImageDraw.Draw(canvas); d.rounded_rectangle((X0, Y0, X1, Y1), 18, outline=PINK, width=10)
    if text:
        f = ImageFont.truetype(FONT_B, 44); tb = d.textbbox((0, 0), text, font=f); tw = tb[2] - tb[0]
        d.rounded_rectangle(((X0 + X1) / 2 - tw / 2 - 20, Y1 + 10, (X0 + X1) / 2 + tw / 2 + 20, Y1 + 80), 30, fill=PINK)
        d.text(((X0 + X1) / 2 - tw / 2, Y1 + 14), text, font=f, fill=(255, 255, 255))

def render(spec, out):
    global GAME_BOX
    if spec.get("game_box"): GAME_BOX = tuple(spec["game_box"])
    recs = {}; frames = []; sounds = []; caps = spec.get("captions", [])
    def R(n):
        if n not in recs: recs[n] = Rec(n)
        return recs[n]
    for seg in spec["segments"]:
        t_out = len(frames) / FPS
        if seg["type"] == "clip":
            r = R(seg["rec"]); a, b = seg["from"], seg["to"]; sp = seg.get("speed", 1.0)
            idx = [int(a + k * sp) for k in range(int((b - a) / sp) + 1)]
            if seg.get("reverse"): idx = idx[::-1]
            frames += [("game", seg["rec"], i) for i in idx]
            if not seg.get("reverse") and sp == 1.0:
                ta, tb = r.t(a), r.t(b)
                for s in r.log["audio"]:
                    st = s["wall"] / 1000.0
                    if ta <= st <= tb: sounds.append((t_out + st - ta, s))
        elif seg["type"] == "hold":
            frames += [("game", seg["rec"], seg["frame"])] * int(seg["dur"] * FPS)
        elif seg["type"] == "book":
            n = int(seg["dur"] * FPS); frames += [("book", seg["image"], k, n) for k in range(n)]
        elif seg["type"] == "pageturn":
            n = int(seg["dur"] * FPS); frames += [("turn", seg["image"], seg["rec"], seg["frame"], k, n) for k in range(n)]; sounds.append((t_out, "page"))
        elif seg["type"] == "end":
            n = int(seg["dur"] * FPS); frames += [("end", seg["text"], seg.get("sub", ""), seg["rec"], seg["frame"])] * n
    total = len(frames) / FPS
    # 소리
    buf = np.zeros(int((total + 1) * SR))
    for at, s in sounds:
        if s == "page": page_sound(buf, at)
        else: tone(buf, at, s)
    buf = np.clip(buf * 1.6, -1, 1); wav = out + ".wav"
    with wave.open(wav, "w") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((buf * 32767).astype(np.int16).tobytes())
    # 화면
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", wav,
                          "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
    cache = {}
    for k, fr in enumerate(frames):
        t = k / FPS
        if fr[0] == "game":
            key = (fr[1], fr[2])
            if key not in cache: cache.clear(); c = BG.copy(); place_game(c, R(fr[1]).img(fr[2])); cache[key] = c
            canvas = cache[key].copy()
        elif fr[0] == "book":
            canvas = storybook(fr[1], fr[2], fr[3])
        elif fr[0] == "turn":
            _, img, rec, fn, kk, n = fr; e = kk / max(n - 1, 1); e = e * e * (3 - 2 * e)
            under = BG.copy(); place_game(under, R(rec).img(fn))
            page = storybook(img, 1, 1); x = int(-W * e)
            canvas = under.copy()
            if x > -W:
                shadow = Image.new("RGBA", (60, H), (60, 30, 10, int(110 * (1 - e)))); canvas.paste(page.crop((-x, 0, W, H)), (0, 0))
                canvas.paste(shadow, (W + x, 0), shadow)
        elif fr[0] == "end":
            canvas = BG.copy(); place_game(canvas, R(fr[3]).img(fr[4]))
            veil = Image.new("RGBA", (W, H), (255, 248, 240, 200)); canvas.paste(veil, (0, 0), veil)
            caption(canvas, fr[1], y=760, size=92, color=PINK, fill=(255, 255, 255, 0))
            if fr[2]: caption(canvas, fr[2], y=920, size=56, fill=(255, 255, 255, 0))
        canvas = canvas.convert("RGBA")
        for c in caps:
            if c["t0"] <= t < c["t1"]:
                if c.get("kind") == "ring": ring(canvas, R(c["rec"]), c["cells"], c.get("text", "여기!"))
                elif c.get("kind") == "ring_box": ring_box(canvas, R(c["rec"]), c["box"], c.get("text", ""))
                elif c.get("kind") == "label": label(canvas, c["text"], (W - 360, 1700) if c.get("pos") == "br" else (60, 1700))
                else: caption(canvas, c["text"], y=c.get("y", 130))
        p.stdin.write(canvas.convert("RGB").tobytes())
    p.stdin.close(); p.wait(); os.remove(wav)
    print(out, f"{total:.1f}s", len(frames), "frames", len(sounds), "sounds")

if __name__ == "__main__":
    render(json.load(open(sys.argv[1])), sys.argv[2])
