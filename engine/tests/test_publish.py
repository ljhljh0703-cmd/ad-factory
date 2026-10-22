"""게시 관문 시험: 임시 폴더에 프로젝트 일부를 복사해 돌린다(실제 요청 기록은 건드리지 않음). 토큰 없음 = 아무것도 보내지 않음."""
import os, sys, json, shutil, tempfile, subprocess
ENG = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ROOT = os.path.dirname(ENG)
tmp = tempfile.mkdtemp()
for d in ["ua/ads", "verify/runs", "judge/runs", "adapters/jelly-panic"]:
    os.makedirs(os.path.join(tmp, d), exist_ok=True)
shutil.copy(os.path.join(ROOT, "ua/ads/posts.json"), os.path.join(tmp, "ua/ads/"))
shutil.copy(os.path.join(ROOT, "ua/ads/A1-flip.mp4"), os.path.join(tmp, "ua/ads/"))
shutil.copytree(os.path.join(ROOT, "verify/runs/V-A1-flip"), os.path.join(tmp, "verify/runs/V-A1-flip"))
shutil.copytree(os.path.join(ROOT, "judge/runs/E004"), os.path.join(tmp, "judge/runs/E004"))
shutil.copy(os.path.join(ROOT, "adapters/jelly-panic/adapter.json"), os.path.join(tmp, "adapters/jelly-panic/"))
env = dict(os.environ, ADF_ROOT=tmp); [env.pop(k, None) for k in ("YOUTUBE_OAUTH_TOKEN", "TIKTOK_ACCESS_TOKEN", "INSTAGRAM_ACCESS_TOKEN")]
def adf(*a):
    r = subprocess.run([sys.executable, "-m", "adf", *a, "--json"], cwd=ENG, env=env, capture_output=True, text=True)
    return (json.loads(r.stdout) if r.returncode == 0 else r.stderr.strip().splitlines()[-1])
rid = adf("publish", "request", "ad=A1-flip")["id"]
with open(os.path.join(tmp, "ua/ads/A1-flip.mp4"), "ab") as f: f.write(b"y")       # 요청 뒤 승인 전에 영상이 바뀜
assert "게시 요청부터" in adf("publish", "approve", f"id={rid}", "who=시험")
rid = adf("publish", "request", "ad=A1-flip")["id"]                               # 다시 요청하면 지금 파일로 점검
assert "승인 없이" in adf("publish", "run", f"id={rid}")
assert "사람 이름" in adf("publish", "approve", f"id={rid}", "who=AI")
assert adf("publish", "approve", f"id={rid}", "who=시험")["상태"] == "승인"
with open(os.path.join(tmp, "ua/ads/A1-flip.mp4"), "ab") as f: f.write(b"x")       # 승인 뒤 영상이 바뀜
assert "바뀌었습니다" in adf("publish", "run", f"id={rid}")
rid = adf("publish", "request", "ad=A1-flip")["id"]; adf("publish", "approve", f"id={rid}", "who=시험")
assert adf("publish", "run", f"id={rid}")["상태"] == "연습완료"                      # 토큰 없음: 보내지 않음
assert adf("publish", "audit")["온전함"] is True
p = os.path.join(tmp, "runs/publish/audit.jsonl"); L = open(p).read().splitlines()
r = json.loads(L[1]); r["때"] = "2000-01-01T00:00:00"; L[1] = json.dumps(r, ensure_ascii=False); open(p, "w").write("\n".join(L) + "\n")       # 감사 기록 한 줄 고침
assert adf("publish", "audit")["온전함"] is False
shutil.rmtree(tmp); print("통과")
