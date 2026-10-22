"""클라우드 세션 중계.

맥 앱은 AI 단계에서 요청문만 남기고 멈춘다(외부응답대기). `sync push` 로 저장소에 올리면,
Code 탭의 클라우드 세션이 `answer --push` 로 기다리는 요청마다 claude -p 를 불러 응답을 넣고 올린다.
맥 앱은 `sync pull` 로 받아 대기열을 이어 돌린다. 클라우드 쪽은 응답 파일만 더하므로 서로 덮어쓰지 않는다.
"""
import os, glob, json, subprocess

from . import paths, providers


def pending():
    out = []
    for req in sorted(glob.glob(paths.p("runs", "jobs", "B*", "request-*.md"))):
        res = req.replace("request-", "response-")[:-3] + ".txt"
        if not os.path.exists(res) or not open(res, encoding="utf-8").read().strip():
            out.append(req)
    return out


def answer(limit=50, model_default="claude-sonnet-5-5"):
    import shutil
    exe = os.environ.get("ADF_CLAUDE") or shutil.which("claude")
    if not exe: raise RuntimeError("claude 명령이 없습니다(Code 탭 클라우드 세션에서 돌리세요)")
    done = []
    for req in pending()[:limit]:
        key = os.path.basename(req)[len("request-"):-3]
        mf = req[:-3] + ".meta.json"
        meta = json.load(open(mf, encoding="utf-8")) if os.path.exists(mf) else {}
        body = open(req, encoding="utf-8").read()
        prompt = "\n".join(l for l in body.split("\n") if not l.startswith("[이미지] "))
        imgs = [paths.p(i) for i in meta.get("images", [])]
        text, m = providers.call_claude(exe, prompt, meta.get("model", model_default), imgs or None)
        base = req.replace("request-", "response-")[:-3]
        open(base + ".txt", "w", encoding="utf-8").write(text)
        json.dump({**m, "제공자": "cloud-session"}, open(base + ".meta.json", "w", encoding="utf-8"), ensure_ascii=False)
        done.append({"작업": os.path.basename(os.path.dirname(req)), "열쇠": key, "토큰": [m["입력_토큰"], m["출력_토큰"]], "초": round((m.get("걸린_ms") or 0) / 1000, 1)})
    return done


def git(*a):
    r = subprocess.run(["git", *a], cwd=paths.ROOT, capture_output=True, text=True)
    if r.returncode != 0: raise RuntimeError(f"git {' '.join(a)}: {(r.stderr or r.stdout).strip()[-600:]}")
    return r.stdout.strip()


def push(msg):
    git("add", "-A")
    if not git("status", "--porcelain"):
        git("pull", "--rebase", "--autostash"); return {"올림": False, "이유": "바뀐 것 없음"}
    git("commit", "-m", msg)
    git("pull", "--rebase", "--autostash")
    git("push")
    return {"올림": True, "커밋": git("rev-parse", "--short", "HEAD")}


def pull():
    before = git("rev-parse", "--short", "HEAD")
    git("pull", "--rebase", "--autostash")
    return {"전": before, "후": git("rev-parse", "--short", "HEAD"), "기다리는_요청": len(pending())}
