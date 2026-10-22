"""게시: 사람 승인 관문 + 바꿀 수 없는 감사 기록.

순서: 요청(자동 점검) → 사람 승인(영상 해시를 함께 묶음) → 실행(해시가 그대로일 때만) → 감사 기록
- 자동 점검: 심사 통과, 녹화본 대조 통과, 게임이 게시 허락됨, 링크에 src·ad 꼬리표, AI 표시 켬
- 승인 뒤 영상이나 글이 한 글자라도 바뀌면 실행을 막는다(다시 승인)
- 실제 업로드는 채널 토큰이 있을 때만. 없으면 「연습」으로 기록하고 아무것도 보내지 않는다
- 감사 기록은 줄마다 앞 줄 해시를 품어, 중간 줄을 고치면 검사에서 드러난다
"""
import json, os, re, glob, hashlib, datetime

from . import paths

# 게시 채널: 작가 결정 10-22 「릴스·쇼츠 둘」(틱톡 내림). 광고 하나를 채널마다 따로 요청하고, 링크 꼬리표 src 로 반응을 채널별로 센다
CHANNEL_KEYS = {"유튜브 쇼츠": ("youtube", "YOUTUBE_OAUTH_TOKEN"), "인스타그램 릴스": ("instagram", "INSTAGRAM_ACCESS_TOKEN")}
CHANNEL_SRC = {"유튜브 쇼츠": "shorts", "인스타그램 릴스": "reels"}
SHORT = {"youtube": "유튜브 쇼츠", "shorts": "유튜브 쇼츠", "instagram": "인스타그램 릴스", "reels": "인스타그램 릴스"}


def channels(ad):
    post = json.load(open(paths.p("ua", "ads", "posts.json"), encoding="utf-8"))[ad]
    return post.get("채널들") or [post["채널"]]


def channel_post(ad, channel):
    """광고 글을 채널에 맞춘 꼴: 채널 이름, 링크의 src 꼬리표, 채널별로 따로 적은 칸(채널별_글)을 덮어씀. 승인 해시는 이 꼴로 묶는다."""
    base = json.load(open(paths.p("ua", "ads", "posts.json"), encoding="utf-8"))[ad]
    post = {k: v for k, v in base.items() if k not in ("채널들", "채널별_글")}
    post.update((base.get("채널별_글") or {}).get(channel, {}))
    post["채널"] = channel
    src = CHANNEL_SRC.get(channel)
    if src: post["링크"] = re.sub(r"([?&])src=[^&]*", rf"\g<1>src={src}", post["링크"]) if "src=" in post["링크"] else post["링크"] + ("&" if "?" in post["링크"] else "?") + f"src={src}"
    return post


def _post_hash(post): return hashlib.sha256(json.dumps(post, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


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


def request(ad, game=None, channel=None):
    """채널을 안 주면 그 광고의 채널마다 하나씩 요청하고 목록을 돌려준다."""
    if channel is None:
        return [request(ad, game, c) for c in channels(ad)]
    channel = SHORT.get(channel, channel)
    if channel not in channels(ad): raise ValueError(f"{ad} 는 {channel} 에 올리는 광고가 아님: {channels(ad)}")
    post = channel_post(ad, channel); game = game or post.get("게임", "jelly-panic"); video = paths.p("ua", "ads", f"{ad}.mp4")
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
           "영상_해시": _sha(video) if os.path.exists(video) else None, "글_해시": _post_hash(post),
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
    video = paths.p(r["영상"])
    now_post = _post_hash(channel_post(r["광고"], r["채널"]))
    if not os.path.exists(video) or _sha(video) != r["영상_해시"] or now_post != r["글_해시"]:
        # 점검은 요청 때 파일로 했다. 그 뒤 바뀐 파일을 승인하면 점검 안 된 것을 승인하게 된다(10-22 녹화 리허설에서 발견)
        audit("막음", 요청=rid, 이유="요청 뒤 영상이나 글이 바뀜(승인 전)")
        raise ValueError("요청 뒤 영상이나 글이 바뀌었습니다. 게시 요청부터 다시 하세요")
    r.update({"상태": "승인", "승인": {"누가": who, "때": now(), "메모": note, "영상_해시": r["영상_해시"], "글_해시": r["글_해시"]}})
    _save(r); audit("승인", 요청=rid, 누가=who, 영상_해시=r["영상_해시"][:16])
    return r


def run(rid):
    r = _load(rid)
    if r["상태"] != "승인" or not r.get("승인"): raise PermissionError("사람 승인 없이 게시할 수 없습니다")
    video = paths.p(r["영상"])
    now_post = _post_hash(channel_post(r["광고"], r["채널"]))
    if _sha(video) != r["승인"]["영상_해시"] or now_post != r["승인"]["글_해시"]:
        r["상태"] = "승인무효(바뀜)"; _save(r); audit("막음", 요청=rid, 이유="승인 뒤 영상이나 글이 바뀜")
        raise PermissionError("승인 뒤 영상이나 글이 바뀌었습니다. 다시 승인하세요")
    ch, env = CHANNEL_KEYS[r["채널"]]
    if ch == "youtube":
        from . import youtube
        if youtube.ready():  # 처음 올림은 비공개. 공개는 make_public 에서 사람 이름으로
            res = youtube.upload(video, r["글"], "private", synthetic="AI 생성" in str(r["글"].get("AI표시", "")))
            r.update({"상태": "게시됨(비공개)", "게시": res}); _save(r); audit("게시", 요청=rid, 채널=ch, 공개="비공개", 결과=res)
            return r
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


UPLOADERS = {"youtube": _not_ready, "instagram": _not_ready}


def make_public(rid, who):
    """비공개로 올린 영상을 사람 이름으로 공개 전환(작가가 폰에서 확인한 뒤)."""
    r = _load(rid)
    if r["상태"] not in ("게시됨(비공개)", "게시됨(일부공개)"): raise ValueError(f"공개로 바꿀 수 없는 상태: {r['상태']}")
    if not who or who in ("AI", "엔진"): raise ValueError("공개 전환은 사람 이름으로만")
    from . import youtube
    st = youtube.set_privacy(r["게시"]["영상_id"], "public")
    r["상태"] = "게시됨"; r["게시"]["공개"] = st; r["공개_승인"] = {"누가": who, "때": now()}; _save(r)
    audit("공개", 요청=rid, 누가=who, 영상=r["게시"]["영상_id"])
    return r


def make_unlisted(rid, who):
    """비공개 영상을 일부 공개(링크 아는 사람만)로. 폰에서 채널 로그인 없이 확인할 때."""
    r = _load(rid)
    if r["상태"] != "게시됨(비공개)": raise ValueError(f"일부 공개로 바꿀 수 없는 상태: {r['상태']}")
    if not who or who in ("AI", "엔진"): raise ValueError("사람 이름으로만")
    from . import youtube
    st = youtube.set_privacy(r["게시"]["영상_id"], "unlisted")
    r["상태"] = "게시됨(일부공개)"; r["게시"]["공개"] = st; r["일부공개_승인"] = {"누가": who, "때": now()}; _save(r)
    audit("일부공개", 요청=rid, 누가=who, 영상=r["게시"]["영상_id"])
    return r


def withdraw(rid, why):
    """요청 내림(채널을 접었을 때 등). 파일은 지우지 않고 상태만 바꾸고 감사 기록에 남긴다."""
    r = _load(rid)
    if r["상태"] == "게시됨": raise ValueError("이미 게시된 요청은 내릴 수 없습니다(채널에서 직접 내리기)")
    r["상태"] = "내림"; r["내림"] = {"때": now(), "이유": why}; _save(r); audit("내림", 요청=rid, 이유=why)
    return r


def requests():
    return [json.load(open(f, encoding="utf-8")) for f in sorted(glob.glob(os.path.join(pdir("requests"), "*.json")))]
