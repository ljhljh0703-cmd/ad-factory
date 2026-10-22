"""AI 모델 호출을 한 곳으로 모은다.

- api      : ANTHROPIC_API_KEY 가 있으면 바로 부른다. 토큰 수는 응답의 usage 값.
- session  : 키가 없을 때. 요청문을 작업 폴더에 request-N.md 로 두고 '외부응답대기'로 멈춘다.
             Claude 세션(또는 사람)이 response-N.txt 를 쓰면 같은 작업을 다시 돌려 이어 간다.
             토큰 수는 글자 수로 어림하고 '추정'으로 표시한다.
- replay   : 예전에 받은 응답 파일을 그대로 다시 쓴다. 회귀 검사에서 돈을 쓰지 않고 판정 합치기·채점만 다시 볼 때.
"""
import os, shutil
from .jobs import Wait
from . import paths


def estimate_tokens(text):
    # 한국어가 섞인 글은 글자 2개 남짓이 토큰 하나 정도. 어림값이며 기록에 '추정'으로 남긴다.
    return max(1, int(len(text) / 2.2))


class Provider:
    name = "?"

    def complete(self, job, key, prompt, model, max_tokens=16000, images=None):
        raise NotImplementedError


class ApiProvider(Provider):
    name = "api"

    def complete(self, job, key, prompt, model, max_tokens=16000, images=None):
        import anthropic, base64
        content = [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                    "data": base64.b64encode(open(i, "rb").read()).decode()}} for i in (images or [])]
        content.append({"type": "text", "text": prompt})
        m = anthropic.Anthropic().messages.create(model=model, max_tokens=max_tokens,
                                                  messages=[{"role": "user", "content": content}])
        text = "".join(b.text for b in m.content if b.type == "text")
        job.model_call(self.name, model, {"입력_토큰": m.usage.input_tokens, "출력_토큰": m.usage.output_tokens, "추정": False})
        return text


class SessionProvider(Provider):
    """요청문을 작업 폴더에 두고 응답 파일을 기다린다. 응답은 클라우드 세션(adf answer)이나 사람이 넣는다.
    응답 옆에 response-<열쇠>.meta.json 이 있으면 실제 토큰 수를 쓰고, 없으면 글자 수로 어림한다."""
    name = "session"

    def complete(self, job, key, prompt, model, max_tokens=16000, images=None):
        import json as js
        req = os.path.join(job.dir, f"request-{key}.md")
        res = os.path.join(job.dir, f"response-{key}.txt")
        meta_req = os.path.join(job.dir, f"request-{key}.meta.json")
        imgs = [paths.rel(i) for i in (images or [])]
        extra = "".join(f"\n[이미지] {i}" for i in imgs)
        body = prompt + extra
        if not os.path.exists(req) or open(req, encoding="utf-8").read() != body:
            # 요청문이 바뀌었으면 예전 응답은 버린다(다른 질문에 대한 답이므로)
            open(req, "w", encoding="utf-8").write(body)
            js.dump({"model": model, "images": imgs, "max_tokens": max_tokens}, open(meta_req, "w", encoding="utf-8"), ensure_ascii=False)
            for f in (res, res[:-4] + ".meta.json"):
                if os.path.exists(f): os.replace(f, f + ".old")
            if job.d.get("비용"): job.d["비용"]["호출"] = [c for c in job.d["비용"]["호출"] if c.get("열쇠") != key]
        if not os.path.exists(res) or not open(res, encoding="utf-8").read().strip():
            raise Wait("외부응답대기", f"{os.path.basename(req)} 에 대한 응답을 {os.path.basename(res)} 로 넣으면 이어 갑니다")
        text = open(res, encoding="utf-8").read()
        if not any(c.get("열쇠") == key for c in (job.d.get("비용") or {}).get("호출", [])):
            mf = res[:-4] + ".meta.json"
            if os.path.exists(mf):
                m = js.load(open(mf, encoding="utf-8"))
                job.model_call(m.get("제공자", "cloud-session"), m.get("모델", model), {"열쇠": key, "입력_토큰": m.get("입력_토큰", 0), "출력_토큰": m.get("출력_토큰", 0),
                                                                                        "추정": False, "구독_환산_달러": m.get("구독_환산_달러"), "걸린_ms": m.get("걸린_ms")})
            else:
                job.model_call(self.name, model, {"열쇠": key, "입력_토큰": estimate_tokens(prompt), "출력_토큰": estimate_tokens(text), "추정": True})
        return text


class ReplayProvider(Provider):
    name = "replay"

    def __init__(self, source):
        self.source = source  # {key: 예전 응답 파일 경로}

    def complete(self, job, key, prompt, model, max_tokens=16000, images=None):
        src = self.source[key]
        shutil.copy(src, os.path.join(job.dir, f"response-{key}.txt"))
        job.input(src, f"다시 쓴 응답 {key}")
        job.model_call(self.name, model, {"열쇠": key, "입력_토큰": 0, "출력_토큰": 0, "추정": False})
        return open(src, encoding="utf-8").read()


class ClaudeCodeProvider(Provider):
    """작가의 Claude Code 로그인(구독)으로 부른다: claude -p. API 키가 필요 없다.
    빈 임시 폴더에서 돌려 볼트의 CLAUDE.md·설정이 판정에 섞이지 않게 하고, 도구는 끈다(이미지가 있을 때만 읽기 허용)."""
    name = "claude-code"

    def __init__(self, exe=None):
        import shutil as sh
        self.exe = exe or os.environ.get("ADF_CLAUDE") or sh.which("claude")

    def complete(self, job, key, prompt, model, max_tokens=16000, images=None):
        open(os.path.join(job.dir, f"request-{key}.md"), "w", encoding="utf-8").write(prompt)
        text, meta = call_claude(self.exe, prompt, model, images)
        open(os.path.join(job.dir, f"response-{key}.txt"), "w", encoding="utf-8").write(text)
        job.model_call(self.name, model, {"열쇠": key, **{k: meta[k] for k in ("입력_토큰", "출력_토큰", "구독_환산_달러", "걸린_ms")}, "추정": False})
        return text


def call_claude(exe, prompt, model, images=None):
    """claude -p 한 번. 빈 임시 폴더에서, 도구 없이(이미지가 있으면 읽기만) 돌린다."""
    import subprocess, tempfile, json as js
    body = prompt
    cmd = [exe, "-p", "--output-format", "json", "--model", model, "--no-session-persistence", "--strict-mcp-config"]
    if images:
        body += "\n\n아래 이미지 파일을 Read 도구로 모두 열어 보고 판정한다:\n" + "\n".join(os.path.abspath(i) for i in images)
        cmd += ["--tools", "Read", "--allowedTools", "Read", "--add-dir", os.path.dirname(os.path.abspath(images[0]))]
    else:
        cmd += ["--tools", ""]
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run(cmd, input=body, capture_output=True, text=True, cwd=tmp, timeout=1800)
    if r.returncode != 0:
        raise RuntimeError(f"claude -p 실패({r.returncode}): {(r.stderr or r.stdout).strip()[-800:]}")
    out = js.loads(r.stdout)
    if out.get("is_error"):
        raise RuntimeError(f"claude -p 오류: {str(out.get('result'))[:500]}")
    u = out.get("usage") or {}; mu = (out.get("modelUsage") or {}).get(model, {})
    meta = {"모델": model, "입력_토큰": ((mu.get("inputTokens") or 0) + (mu.get("cacheReadInputTokens") or 0) + (mu.get("cacheCreationInputTokens") or 0)) or u.get("input_tokens", 0),
            "출력_토큰": mu.get("outputTokens") or u.get("output_tokens", 0), "구독_환산_달러": out.get("total_cost_usd"), "걸린_ms": out.get("duration_api_ms")}
    return out.get("result") or "", meta


def pick(name=None, replay=None):
    if replay:
        return ReplayProvider(replay)
    name = name or os.environ.get("ADF_PROVIDER")
    if name == "api" or (name is None and os.environ.get("ANTHROPIC_API_KEY")):
        return ApiProvider()
    if name == "claude-code" or (name is None and ClaudeCodeProvider().exe):
        return ClaudeCodeProvider()
    return SessionProvider()
