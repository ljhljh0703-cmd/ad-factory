"""작업 대기열과 실행 기록.

작업 하나 = 단계 하나(생성·심사·장면 찾기·녹화·편집·녹화본 대조 …).
모든 작업은 runs/jobs/<작업번호>/job.json 에 입력 파일(해시)·모델·비용·산출 파일(해시)·걸린 시간·상태를 남긴다.
화면(앱)은 이 파일만 읽는다. 엔진과 화면 사이에 다른 길은 없다.
"""
import json, os, hashlib, datetime, time, traceback, fcntl, glob

from . import paths

STATES = ("대기", "실행", "외부응답대기", "사람확인대기", "완료", "실패", "막음")


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def sha(path):
    if not os.path.exists(path):
        return None
    if os.path.isdir(path):
        h = hashlib.sha256()
        for p in sorted(glob.glob(os.path.join(path, "**", "*"), recursive=True)):
            if os.path.isfile(p):
                h.update(os.path.relpath(p, path).encode()); h.update(open(p, "rb").read())
        return "dir:" + h.hexdigest()[:16]
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]


def jobs_dir():
    d = os.path.join(paths.ROOT, "runs", "jobs"); os.makedirs(d, exist_ok=True); return d


def _next_id():
    lock = open(os.path.join(jobs_dir(), ".lock"), "w")
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
        n = 1 + max([int(os.path.basename(p)[1:]) for p in glob.glob(os.path.join(jobs_dir(), "B*")) if os.path.basename(p)[1:].isdigit()] or [0])
        jid = f"B{n:04d}"; os.makedirs(os.path.join(jobs_dir(), jid))
        return jid
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)


class Job:
    def __init__(self, data):
        self.d = data

    @property
    def id(self): return self.d["id"]

    @property
    def dir(self): return os.path.join(jobs_dir(), self.id)

    def save(self):
        tmp = os.path.join(self.dir, "job.json.tmp")
        json.dump(self.d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, os.path.join(self.dir, "job.json"))

    def log(self, msg):
        with open(os.path.join(self.dir, "log.txt"), "a", encoding="utf-8") as f:
            f.write(f"{now()} {msg}\n")

    # 단계가 부르는 기록 함수
    def _rec(self, key, path, role):
        r = {"파일": paths.rel(path), "해시": sha(path), "역할": role}
        self.d[key] = [x for x in self.d[key] if x["파일"] != r["파일"]] + [r]; self.save()

    def input(self, path, role=""): self._rec("입력", path, role)

    def output(self, path, role=""): self._rec("산출", path, role)

    def model_call(self, provider, model, usage):
        """usage: {"입력_토큰", "출력_토큰", "추정"(bool)}. 값은 prices.json 으로 계산, 가격이 없으면 비워 둔다."""
        if not self.d.get("비용"):
            self.d["비용"] = {"호출": [], "입력_토큰": 0, "출력_토큰": 0, "달러": None, "추정_포함": False}
        c = self.d["비용"]
        c["호출"].append({"제공자": provider, "모델": model, **usage})
        c["입력_토큰"] += usage.get("입력_토큰") or 0
        c["출력_토큰"] += usage.get("출력_토큰") or 0
        c["추정_포함"] = c["추정_포함"] or bool(usage.get("추정"))
        if usage.get("구독_환산_달러") is not None:
            c["구독_환산_달러"] = round((c.get("구독_환산_달러") or 0) + usage["구독_환산_달러"], 4)
        price = paths.prices().get(model)
        if price:
            c["달러"] = round(c["입력_토큰"] / 1e6 * price["입력"] + c["출력_토큰"] / 1e6 * price["출력"], 4)
        self.d["모델"] = model; self.d["제공자"] = provider
        self.save()


def create(stage, args, after=None, pipeline=None, note=""):
    jid = _next_id()
    j = Job({"id": jid, "단계": stage, "인자": args, "상태": "대기", "앞_작업": after or [], "묶음": pipeline,
             "메모": note, "입력": [], "산출": [], "모델": None, "제공자": None, "비용": None,
             "만든_때": now(), "시작": None, "끝": None, "걸린_초": None, "오류": None, "결과": None})
    j.save()
    return j


def get(jid):
    return Job(json.load(open(os.path.join(jobs_dir(), jid, "job.json"), encoding="utf-8")))


def all_jobs():
    out = []
    for p in sorted(glob.glob(os.path.join(jobs_dir(), "B*", "job.json"))):
        try: out.append(Job(json.load(open(p, encoding="utf-8"))))
        except (json.JSONDecodeError, OSError): pass
    return out


class Wait(Exception):
    """외부(Claude 세션·사람) 응답을 기다린다. 응답 파일이 생기면 같은 작업을 다시 돌린다."""
    def __init__(self, state, msg):
        super().__init__(msg); self.state = state


class Blocked(Exception):
    """관문에 걸려 뒤 단계로 넘기지 않는다(예: 사실표 어긋남, 비싼 오류)."""


def ready(j, index):
    if j.d["상태"] not in ("대기", "외부응답대기", "사람확인대기"):
        return False
    return all(index.get(a) and index[a].d["상태"] == "완료" for a in j.d["앞_작업"])


def run_one(j):
    from . import stages
    fn = stages.REGISTRY[j.d["단계"]]
    j.d.update({"상태": "실행", "시작": j.d["시작"] or now(), "오류": None}); j.save(); j.log("시작")
    t = time.time()
    try:
        res = fn(j, **j.d["인자"])
        j.d.update({"상태": "완료", "결과": res})
        j.log("완료")
    except Wait as w:
        j.d.update({"상태": w.state, "결과": str(w)}); j.log(f"{w.state}: {w}")
    except Blocked as b:
        j.d.update({"상태": "막음", "결과": str(b)}); j.log(f"막음: {b}")
    except Exception as e:
        j.d.update({"상태": "실패", "오류": f"{type(e).__name__}: {e}"})
        j.log(traceback.format_exc())
    j.d["걸린_초"] = round((j.d["걸린_초"] or 0) + time.time() - t, 2)
    if j.d["상태"] in ("완료", "실패", "막음"):
        j.d["끝"] = now()
    j.save()
    return j


def run_queue(max_jobs=1000):
    """앞 작업이 끝난 것부터 차례로 돌린다. 막힘·실패가 나면 그 뒤 작업은 그대로 둔다."""
    done, tried = 0, set()
    while done < max_jobs:
        idx = {j.id: j for j in all_jobs()}
        # 기다리던 작업은 한 번씩만 다시 본다(응답 파일이 생겼는지). 없으면 다시 기다림으로 남는다.
        nxt = [j for j in idx.values() if ready(j, idx) and j.id not in tried]
        if not nxt:
            break
        tried.add(nxt[0].id); run_one(nxt[0]); done += 1
    return done
