"""유튜브 업로더(공식 YouTube Data API v3, 표준 라이브러리만).

열쇠 파일: 저장소 안 `.local/youtube.json`(.gitignore 로 올라가지 않음) 또는 환경 변수 ADF_YOUTUBE_CRED 가 가리키는 파일.
  {"client_id", "client_secret", "refresh_token", "channel_id"}
권한 받기(한 번):
  python3 -m adf youtube client file=<내려받은 client_secret.json>   # OAuth 클라이언트 정보만 열쇠 파일에 옮김
  python3 -m adf youtube auth-url                                   # 이 주소를 브라우저에서 열어 「젤리 패닉」 채널을 고르고 허용
  python3 -m adf youtube auth-code url=<허용 뒤 넘어간 주소>          # 갱신 토큰을 열쇠 파일에 저장
올리기는 게시 관문(publish.run)에서만 부른다. 처음 올림은 비공개, 공개 전환은 사람 승인 이름이 있어야 한다.
"""
import json, os, urllib.parse, urllib.request

from . import paths

# 공개 범위 바꾸기(videos.update)는 upload 권한으로 안 됨(10-22 403) → youtube 관리 권한
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube",
          "https://www.googleapis.com/auth/yt-analytics.readonly"]
REDIRECT = "http://localhost:8765/"
CHANNEL_ID = "UCClbeVRufxz-skvVC6OFPQQ"  # 「젤리 패닉」 채널(작가 계정, 10-22 이름 바꿔 씀)


def cred_path():
    return os.environ.get("ADF_YOUTUBE_CRED") or paths.p(".local", "youtube.json")


def load():
    p = cred_path()
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def save(d):
    p = cred_path(); os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.chmod(p, 0o600)


def ready():
    c = load(); return bool(c.get("refresh_token") and c.get("client_id"))


def set_client(file):
    j = json.load(open(file, encoding="utf-8")); j = j.get("installed") or j.get("web") or j
    c = load(); c.update(client_id=j["client_id"], client_secret=j["client_secret"]); save(c)
    return {"열쇠_파일": cred_path(), "클라이언트": j["client_id"][:12] + "…"}


def auth_url():
    c = load()
    if not c.get("client_id"): raise RuntimeError("OAuth 클라이언트가 없습니다: youtube client file=… 먼저")
    q = {"client_id": c["client_id"], "redirect_uri": REDIRECT, "response_type": "code", "scope": " ".join(SCOPES),
         "access_type": "offline", "prompt": "consent select_account", "include_granted_scopes": "true"}
    return {"주소": "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(q)}


def _post(url, data, headers=None):
    body = urllib.parse.urlencode(data).encode() if isinstance(data, dict) else data
    req = urllib.request.Request(url, data=body, headers=headers or {}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read() or b"{}")


def auth_code(url_or_code):
    code = urllib.parse.parse_qs(urllib.parse.urlparse(url_or_code).query).get("code", [url_or_code])[0]
    c = load()
    t = _post("https://oauth2.googleapis.com/token", {"code": code, "client_id": c["client_id"], "client_secret": c["client_secret"],
                                                      "redirect_uri": REDIRECT, "grant_type": "authorization_code"})
    if not t.get("refresh_token"): raise RuntimeError("갱신 토큰이 오지 않았습니다(권한 화면을 처음부터 다시)")
    c["refresh_token"] = t["refresh_token"]; save(c)
    me = channel(token=t["access_token"])
    c["channel_id"] = me.get("id"); save(c)
    ok = me.get("id") == CHANNEL_ID
    return {"채널": me.get("title"), "채널_id": me.get("id"), "젤리_패닉_채널": ok,
            **({} if ok else {"경고": "고른 채널이 젤리 패닉이 아닙니다. 권한 화면에서 젤리 패닉 채널을 골라 다시 하세요. 이 상태로는 올리지 않습니다"})}


def access_token():
    c = load()
    if not c.get("refresh_token"): raise RuntimeError("유튜브 권한이 없습니다(youtube auth-url 부터)")
    return _post("https://oauth2.googleapis.com/token", {"client_id": c["client_id"], "client_secret": c["client_secret"],
                                                         "refresh_token": c["refresh_token"], "grant_type": "refresh_token"})["access_token"]


def _get(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read())


def channel(token=None):
    token = token or access_token()
    items = _get("https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true", token).get("items") or []
    return {"id": items[0]["id"], "title": items[0]["snippet"]["title"]} if items else {}


def _description(post):
    tags = " ".join("#" + t for t in post.get("태그") or [])
    return f"{post['글']}\n\n{post['링크']}\n\n{tags}".strip()


def upload(video, post, privacy="private", synthetic=False):
    """처음 올림은 비공개. 올린 채널이 젤리 패닉이 아니면 올리지 않는다."""
    c = load()
    if c.get("channel_id") != CHANNEL_ID: raise PermissionError("권한 받은 채널이 젤리 패닉이 아닙니다")
    token = access_token()
    meta = {"snippet": {"title": (post.get("제목") or post["글"])[:100], "description": _description(post)[:5000],
                        "tags": post.get("태그") or [], "categoryId": "20"},  # 20 = 게임
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False, "containsSyntheticMedia": bool(synthetic)}}
    size = os.path.getsize(video)
    init = urllib.request.Request("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                                  data=json.dumps(meta).encode(), method="POST",
                                  headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
                                           "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)})
    with urllib.request.urlopen(init, timeout=60) as r: loc = r.headers["Location"]
    put = urllib.request.Request(loc, data=open(video, "rb").read(), method="PUT",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "video/mp4"})
    with urllib.request.urlopen(put, timeout=600) as r: v = json.loads(r.read())
    return {"영상_id": v["id"], "주소": f"https://youtube.com/shorts/{v['id']}", "공개": v["status"]["privacyStatus"],
            "합성_표시": v["status"].get("containsSyntheticMedia")}


def set_privacy(video_id, privacy):
    token = access_token()
    cur = _get(f"https://www.googleapis.com/youtube/v3/videos?part=status&id={video_id}", token)["items"][0]["status"]
    cur["privacyStatus"] = privacy
    req = urllib.request.Request("https://www.googleapis.com/youtube/v3/videos?part=status", method="PUT",
                                 data=json.dumps({"id": video_id, "status": cur}).encode(),
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read())["status"]["privacyStatus"]


def stats(video_id):
    """반응 숫자: 재생·좋아요·댓글(유튜브는 저장 수를 주지 않아 비움, 공유는 분석 API)."""
    s = _get(f"https://www.googleapis.com/youtube/v3/videos?part=statistics&id={video_id}", access_token())["items"][0]["statistics"]
    return {"재생": int(s.get("viewCount", 0)), "좋아요": int(s.get("likeCount", 0)), "댓글": int(s.get("commentCount", 0)), "공유": None, "저장": None}
