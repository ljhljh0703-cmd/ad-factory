"""게시: 사람 승인 관문 + 바꿀 수 없는 감사 기록.

순서: 요청(자동 점검) → 사람 승인(영상 해시를 함께 묶음) → 실행(해시가 그대로일 때만) → 감사 기록
- 자동 점검: 심사 통과, 녹화본 대조 통과, 게임이 게시 허락됨, 링크에 src·ad 꼬리표, AI 표시 켬
- 승인 뒤 영상이나 글이 한 글자라도 바뀌면 실행을 막는다(다시 승인)
- 실제 업로드는 채널 토큰이 있을 때만. 없으면 「연습」으로 기록하고 아무것도 보내지 않는다
- 감사 기록은 줄마다 앞 줄 해시를 품어, 중간 줄을 고치면 검사에서 드러난다
"""
import json, os, glob, hashlib, datetime

from . import paths

CHANNEL_KEYS = {"유튜브 쇼츠": ("youtube", "YOUTUBE_OAUTH_TOKEN"), "틱톡": ("tiktok", "TIKTOK_ACCESS_TOKEN"),
                "인스타그램 릴스": ("instagram", "INSTAGRAM_ACCESS_TOKEN")}


def pdir(sub=None):
    d = paths.p("runs", "publish", *([sub] if sub else [])); os.makedirs(d, exist_ok=True); return d


def now(): return datetime.datetime.now().isoformat(timespec="seconds")


def _sha(path): return hashlib.sha256(open(path, "rb").read()).hexdigest()


def audit(event, **kw):
    f = os.path.join(pdir(), "audit.jsonl")
    prev = "0" * 64
    if os.path.exists(f):
        lines = [l for l in open(f, encoding="utf-8") if l.strip()]
        if lines: prev = json.loads(lines[-1])["줄_해시"]
    row = {"때": now(), "일": event, **kw, "앞_해시": prev}
    row["줄_해시"] = hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    with open(f, "a", encoding="utf-8") as fh: fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def verify_audit():
    f = os.path.join(pdir(), "audit.jsonl"); prev = "0" * 64; n = 0
    if not os.path.exists(f): return {"줄": 0, "온전함": True}
    for i, l in enumerate(open(f, encoding="utf-8")):
        r = json.loads(l); h = r.pop("줄_해시")
        if r["앞_해시"] != prev or hashlib.sha256(json.dumps(r, ensure_ascii=False, sort_keys=True).encode()).hexdigest() != h:
            return {"줄": i + 1, "온전함": False, "깨진_줄": i + 1}
        prev = h; n += 1
    return {"줄": n, "온전함": True}


def _decision(cid):
    """그 소재의 가장 최근 심사 결정."""
    best = None
    for d in sorted(glob.glob(paths.p("judge", "runs", "*", "decisions.jsonl")), key=os.path.getmtime):
        for l in open(d, encoding="utf-8"):
            o = json.loads(l)
            if o["id"] == cid: best = (os.path.basename(os.path.dirname(d)), o["최종"])
    return best


def request(ad, game=None):
    posts = json.load(open(paths.p("ua", "ads", "posts.json"), encoding="utf-8"))
    post = posts[ad]; game = game or post.get("게임", "jelly-panic"); video = paths.p("ua", "ads", f"{ad}.mp4")
    cid = post["링크"].split("ad=")[1].split("&")[0]
    man = json.load(open(paths.p("adapters", game, "adapter.json"), encoding="utf-8"))
    dec = _decision(cid)
    fc = paths.p("verify", "runs", f"V-{ad}", "report.json")
    footage = json.load(open(fc, encoding="utf-8"))["결론"] if os.path.exists(fc) else None
    checks = {
        "심사 통과": bool(dec and dec[1] == "통과"),
        "녹화본 대조 통과": footage == "통과",
        "게시 허락된 게임": man.get("광고_게시", {}).get("가능", False),
        "링크 꼬리표(src·ad)": "src=" in post["링크"] and "ad=" in post["링크"],
        "AI 표시 켬": str(post.get("AI표시", "")).startswith("켬"),
        "영상 있음": os.path.exists(video),
    }
    rid = f"P-{ad}-{CHANNEL_KEYS.get(post['채널'], ('x',))[0]}"
    req = {"id": rid, "광고": ad, "소재": cid, "채널": post["채널"], "글": post, "영상": paths.rel(video),
           "영상_해시": _sha(video) if os.path.exists(video) else None, "글_해시": hashlib.sha256(json.dumps(post, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
           "점검": checks, "심사_회차": dec[0] if dec else None, "상태": "승인대기" if all(checks.values()) else "점검실패",
           "승인": None, "요청_때": now()}
    json.dump(req, open(os.path.join(pdir("requests"), rid + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    audit("요청", 요청=rid, 상태=req["상태"], 점검={k: v for k, v in checks.items()})
    return req


def _load(rid): return json.load(open(os.path.join(pdir("requests"), rid + ".json"), encoding="utf-8"))


def _save(r): json.dump(r, open(os.path.join(pdir("requests"), r["id"] + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def approve(rid, who, note=""):
    r = _load(rid)
    if r["상태"] != "승인대기": raise ValueError(f"승인할 수 없는 상태: {r['상태']}")
    if not who or who in ("AI", "엔진"): raise ValueError("승인은 사람 이름으로만")
    r.update({"상태": "승인", "승인": {"누가": who, "때": now(), "메모": note, "영상_해시": r["영상_해시"], "글_해시": r["글_해시"]}})
    _save(r); audit("승인", 요청=rid, 누가=who, 영상_해시=r["영상_해시"][:16])
    return r


def run(rid):
    r = _load(rid)
    if r["상태"] != "승인" or not r.get("승인"): raise PermissionError("사람 승인 없이 게시할 수 없습니다")
    video = paths.p(r["영상"])
    posts = json.load(open(paths.p("ua", "ads", "posts.json"), encoding="utf-8"))
    now_post = hashlib.sha256(json.dumps(posts[r["광고"]], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    if _sha(video) != r["승인"]["영상_해시"] or now_post != r["승인"]["글_해시"]:
        r["상태"] = "승인무효(바뀜)"; _save(r); audit("막음", 요청=rid, 이유="승인 뒤 영상이나 글이 바뀜")
        raise PermissionError("승인 뒤 영상이나 글이 바뀌었습니다. 다시 승인하세요")
    ch, env = CHANNEL_KEYS[r["채널"]]
    if not os.environ.get(env):
        r["상태"] = "연습완료"; _save(r)
        audit("연습", 요청=rid, 채널=ch, 이유=f"{env} 없음: 아무것도 보내지 않음", 보낼_내용={"제목": r["글"].get("제목"), "글": r["글"]["글"][:80], "링크": r["글"]["링크"]})
        return r
    res = UPLOADERS[ch](video, r["글"], os.environ[env])
    r.update({"상태": "게시됨", "게시": res}); _save(r); audit("게시", 요청=rid, 채널=ch, 결과=res)
    return r


# 채널별 업로더. 토큰이 생기면 여기만 채운다(공식 API: YouTube Data API videos.insert,
# TikTok Content Posting API, Instagram Graph API 릴스 컨테이너). 지금은 계정이 없어 시험하지 않았다.
def _not_ready(video, post, token):
    raise NotImplementedError("채널 계정 연결 전: 업로더를 시험하지 않았습니다")


UPLOADERS = {"youtube": _not_ready, "tiktok": _not_ready, "instagram": _not_ready}


def requests():
    return [json.load(open(f, encoding="utf-8")) for f in sorted(glob.glob(os.path.join(pdir("requests"), "*.json")))]
