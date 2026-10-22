# 광고 공장 홍보영상 조립: 앱 화면 사진 14장 -> 가로 30초 / 세로 15초
import sys, subprocess, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
ROOT = sys.argv[1]; MODE = sys.argv[2]   # h | v
ST = ROOT + '/raw/stills/'
MUSIC = sys.argv[3]
FPS = 30
BOLD = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
REG = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
def font(sz, b=True): return ImageFont.truetype(BOLD if b else REG, sz, index=1)

_cache = {}
def still(name):
    if name not in _cache:
        im = Image.open(ST + name).convert('RGB')
        reg = (0, 800, 260, 860)  # 화면 아래 엔진 경로(사용자 폴더 이름) 흐리게
        im.paste(im.crop(reg).filter(ImageFilter.GaussianBlur(9)), reg[:2])
        _cache[name] = im
    return _cache[name]

B = 0.545; G0 = 0.13
def bar(k): return G0 + 4 * B * k   # 4박 경계

C = [
 '광고 기획부터 게시 승인까지 한 앱에서',
 '게임 문구가 한 글자만 달라도 심사를 막고',
 '사람이 고친 판정은 이유와 함께 시험 묶음으로',
 '기준이 바뀌면 다시 돌리고, 비싼 오류 하나에도 멈춘다',
 '말로 적은 요청도 규칙으로 걸러낸다',
 '승인은 사람 이름으로만',
]
CV = [C[0], '게임 문구가 한 글자만\n달라도 심사를 막고', C[2],
      '기준이 바뀌면 다시 돌리고,\n비싼 오류 하나에도 멈춘다', C[4], C[5]]
END_T = 'AI 기획에서 사람 승인까지'
END_S = '젤리 패닉 광고 소재 공장'
END_N = '이주형 · github.com/ljhljh0703-cmd'

if MODE == 'h':
    W, H = 1920, 1080; CW, CH = 1440, 810; CX, CY = 240, 64; CAPY = 958; CAPSZ = 50
    # (시작, 끝, 사진, 시작 크롭, 끝 크롭, 자막 번호)
    SHOTS = [
     (0.0, bar(2), '01a-home-before.jpg', (0,0,1280,720), (220,120,1250,699), 0),
     (bar(2), bar(3), '02a-facts-blocked.jpg', (230,60,1050,521), (250,110,830,436), 1),
     (bar(3), bar(4), '02b-jobs-blocked.jpg', (160,330,1000,802), (180,430,860,812), 1),
     (bar(4), bar(6), '03b-review-done.jpg', (230,200,1150,717), (240,380,960,785), 2),
     (bar(6), bar(8), '04-regress-blocked-P15.jpg', (230,60,1250,634), (600,180,1240,540), 3),
     (bar(8), bar(9), '05-plan-request-and-check.jpg', (230,60,1050,521), (240,90,960,495), 4),
     (bar(9), bar(10), '05-plan-request-and-check.jpg', (240,420,1000,848), (240,297,1240,860), 4),
     (bar(10), bar(10)+2*B, '06b-approve-blocked-toast.jpg', (520,430,1280,857), (560,455,1280,860), 5),
     (bar(10)+2*B, bar(11), '06c-approve-checked-name.jpg', (200,410,980,849), (230,440,950,845), 5),
     (bar(11), bar(12), '06d-practice-done-audit.jpg', (220,40,1020,490), (230,100,890,471), 5),
    ]
    END0 = bar(12); TOTAL = END0 + 4.3; MOFF = 0.0
    caps = C
else:
    W, H = 1080, 1920; CW, CH = 1000, 760; CX, CY = 40, 420; CAPY = 1290; CAPSZ = 58
    o = bar(6)   # 음악 13.2초 지점부터. 크롭 비율 1000:760
    SHOTS = [
     (bar(6)-o, bar(7)-o, '02a-facts-blocked.jpg', (230,40,1010,633), (240,80,860,551), 1),
     (bar(7)-o, bar(8)-o, '02b-jobs-blocked.jpg', (160,328,860,860), (170,400,770,856), 1),
     (bar(8)-o, bar(10)-o, '04-regress-blocked-P15.jpg', (230,85,1250,860), (560,180,1250,704), 3),
     (bar(10)-o, bar(10)+2*B-o, '06b-approve-blocked-toast.jpg', (560,313,1280,860), (610,359,1270,860), 5),
     (bar(10)+2*B-o, bar(11)-o, '06c-approve-checked-name.jpg', (190,328,890,860), (210,400,800,848), 5),
     (bar(11)-o, bar(12)-o, '06d-practice-done-audit.jpg', (200,40,940,602), (220,90,860,576), 5),
    ]
    END0 = bar(12) - o; TOTAL = END0 + 3.4; MOFF = o
    caps = CV

def ease(t): return t*t*(3-2*t)
def lerp(a, b, t): return tuple(a[i] + (b[i]-a[i]) * t for i in range(4))

# 배경·그림자·모서리
bg = Image.new('RGB', (W, H))
d = ImageDraw.Draw(bg)
for y in range(H):
    c = int(246 - 8 * y / H); d.line([(0, y), (W, y)], fill=(c, c, c + 2))
sh = Image.new('L', (W, H), 0)
ImageDraw.Draw(sh).rounded_rectangle((CX, CY + 14, CX + CW, CY + CH + 14), 22, fill=70)
sh = sh.filter(ImageFilter.GaussianBlur(28))
base = Image.composite(Image.new('RGB', (W, H), (40, 40, 50)), bg, sh)
mask = Image.new('L', (CW, CH), 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, CW-1, CH-1), 20, fill=255)

def card(shot, t):
    s0, s1, name, a, b, _ = shot
    p = ease(min(1, max(0, (t - s0) / (s1 - s0))))
    r = lerp(a, b, p)
    im = still(name).crop(tuple(int(round(v)) for v in r)).resize((CW, CH), Image.BICUBIC)
    return im

def put_text(img, txt, y, sz, col, alpha=1.0, b=True):
    f = font(sz, b); lines = txt.split('\n')
    lay = Image.new('RGBA', img.size, (0, 0, 0, 0)); dd = ImageDraw.Draw(lay)
    for i, ln in enumerate(lines):
        w = dd.textlength(ln, font=f)
        dd.text(((W - w) / 2, y + i * sz * 1.35), ln, font=f, fill=col + (int(255 * alpha),))
    img.paste(lay, (0, 0), lay)

icon = Image.open(ROOT.replace('game-ad-factory/promo', 'game-ops-platform') + '/docs/brand/jelly-panic.png').convert('RGB')
isz = 200 if MODE == 'h' else 240
icon = icon.resize((isz, isz), Image.LANCZOS)
imask = Image.new('L', (isz, isz), 0); ImageDraw.Draw(imask).rounded_rectangle((0, 0, isz-1, isz-1), 44, fill=255)

def frame(t):
    if t >= END0:
        k = min(1, (t - END0) / 0.6)
        img = bg.copy()
        cy = H // 2 - (170 if MODE == 'h' else 260)
        lay = bg.copy(); lay.paste(icon, ((W - isz) // 2, cy), imask)
        img = Image.blend(img, lay, k)
        put_text(img, END_T, cy + isz + 50, 80 if MODE == 'h' else 76, (29, 29, 31), k)
        put_text(img, END_S, cy + isz + 170, 38 if MODE == 'h' else 40, (110, 110, 115), k, False)
        put_text(img, END_N, cy + isz + 225 if MODE == 'h' else cy + isz + 235, 32 if MODE == 'h' else 36, (110, 110, 115), k, False)
        # 끝 쪽 앞 장면에서 넘어오는 0.3초
        if t - END0 < 0.3:
            prev = render_shot(SHOTS[-1], END0 - 0.001)
            img = Image.blend(prev, img, (t - END0) / 0.3)
        return img
    return render_shot(next(s for s in SHOTS if s[0] <= t < s[1]), t)

def render_shot(shot, t):
    i = SHOTS.index(shot)
    img = base.copy(); img.paste(card(shot, t), (CX, CY), mask)
    cap = shot[5]; first = i == 0 or SHOTS[i-1][5] != cap
    # 자막: 장면이 바뀔 때만 떠오름
    s_cap = shot[0] if first else next(s[0] for s in SHOTS if s[5] == cap)
    a = min(1, (t - s_cap) / 0.35)
    put_text(img, caps[cap], CAPY + int(14 * (1 - ease(a))), CAPSZ, (29, 29, 31), a)
    # 컷 사이 짧은 겹침
    if i > 0 and t - shot[0] < 0.18:
        prev = render_shot(SHOTS[i-1], shot[0] - 0.001)
        img = Image.blend(prev, img, (t - shot[0]) / 0.18)
    return img

out = ROOT + ('/out/promo-30s.mp4' if MODE == 'h' else '/out/promo-15s-vertical.mp4')
n = int(TOTAL * FPS)
fade = 2.0
cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
       '-ss', f'{MOFF:.3f}', '-i', MUSIC,
       '-filter_complex', f'[1:a]apad,atrim=0:{TOTAL:.3f},afade=t=in:d=0.05,afade=t=out:st={TOTAL-fade:.3f}:d={fade},volume=0.82,alimiter=limit=0.75:level=false[a]',
       '-map', '0:v', '-map', '[a]', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p',
       '-c:a', 'aac', '-b:a', '192k', '-t', f'{TOTAL:.3f}', '-movflags', '+faststart', out]
p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
for k in range(n):
    p.stdin.write(frame(k / FPS).tobytes())
p.stdin.close(); p.wait()
print(out, TOTAL)
