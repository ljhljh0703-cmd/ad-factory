"""공개용 묶음 내보내기: 웹 보기 화면이 읽는 유일한 자료.

꼴(adf-board/1)을 지키면 화면은 바뀌지 않는다. 나중에 서버를 두면 서버가 같은 꼴을 돌려준다.
넣지 않는 것: 승인한 사람 이름, 처리자 이름, 열쇠·토큰, 채널 계정, 게시가 허락되지 않은 게임의 소재.
"""
import os, json, glob, re, datetime
from . import paths, quality, experiment

FORMAT = "adf-board/1"


def _load(p):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def _lines(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if os.path.exists(p) else []


def games():
    out = {}
    for f in glob.glob(paths.p("adapters", "*", "adapter.json")):
        m = json.load(open(f, encoding="utf-8"))
        out[m["id"]] = {"id": m["id"], "이름": m["이름"], "게시_가능": bool(m.get("광고_게시", {}).get("가능", False))}
    return out


def criteria():
    md = open(paths.p("CRITERIA.md"), encoding="utf-8").read()
    body = md.split("## 변경 기록")[0]
    ids = list(dict.fromkeys(re.findall(r"^\| ((?:G|R)\d+) ", body, re.M)))
    dates = re.findall(r"^- (\d{4}-\d{2}-\d{2})", md.split("## 변경 기록")[-1], re.M)
    return {"판": f"{dates[-1]}#{len(dates)}" if dates else None,
            "통과_조건": sum(i.startswith("G") for i in ids), "반려_조건": sum(i.startswith("R") for i in ids)}


def _set_game(setname):
    rj = _load(paths.p("generator", "runs", setname, "run.json"))
    return (rj or {}).get("game", "jelly-panic")


def judge_history(notes, allowed, replays=()):
    rows = []
    for d in sorted(glob.glob(paths.p("judge", "runs", "*"))):
        m = _load(os.path.join(d, "run.json"))
        if not m: continue
        game = m.get("게임") or _set_game(m["set"])
        if game not in allowed: continue
        s = _load(os.path.join(d, "score.json")) or {}
        rows.append({"회차": m["run"], "묶음": m["set"], "게임": game, "때": m.get("만든_때"), "기준표_판": m.get("기준표_판"),
                     "소재_수": m.get("소재_수"), "판정_일치": s.get("판정_일치"), "반려_재현율": s.get("반려_재현율"), "카파": s.get("카파"),
                     "비싼_오류": len(s.get("비싼_오류(반려를_통과시킴)") or []) if s else None,
                     "채점": bool(s), "메모": notes.get(m["run"], ""), "다시_씀": m["run"] in replays})
    rows.sort(key=lambda r: r["때"] or "")
    return rows


def regress_history():
    st = _load(paths.p("runs", "regress", "state.json")) or {}
    out = []
    for r in st.get("회차", []):
        res = r.get("결과") or {}
        out.append({"id": r["id"], "때": r.get("때"), "바뀐_것": r.get("바뀐_것", []), "관문": res.get("관문", "진행"),
                    "묶음별": {k: {x: v.get(x) for x in ("소재_수", "판정_일치", "카파", "앞_회차_대비")} | {"비싼_오류": len(v.get("비싼_오류(반려를_통과시킴)") or [])}
                              for k, v in (res.get("묶음별") or {}).items()}})
    return out


def _reasons(dec):
    out = []
    for g in dec.get("근거") or []:
        if g.get("조건"): out.append({"조건": g["조건"], "구절": g.get("구절", ""), "사유": g.get("사유", "")})
        elif g.get("사람확인_이유"): out.append({"조건": "사람 확인", "구절": "", "사유": g["사람확인_이유"]})
    seen, uniq = set(), []
    for r in out:  # 두 번 판정이 같은 조건을 잡으면 하나만
        if r["조건"] in seen: continue
        seen.add(r["조건"]); uniq.append(r)
    return uniq


def generated(allowed):
    """생성 회차마다 가장 늦게 돌린 심사의 판정."""
    latest = {}
    for d in glob.glob(paths.p("judge", "runs", "*")):
        m = _load(os.path.join(d, "run.json"))
        if m and os.path.isdir(paths.p("generator", "runs", m["set"])):
            if m["set"] not in latest or (m.get("만든_때") or "") > (latest[m["set"]][0] or ""):
                latest[m["set"]] = (m.get("만든_때"), d)
    out = []
    for setname in sorted(latest):
        game = _set_game(setname)
        if game not in allowed: continue
        cands = {c["id"]: c for c in _lines(paths.p("generator", "runs", setname, "candidates.jsonl"))}
        gold = {o["id"]: {"판정": o["정답"], "조건": o.get("걸린것") or [], "근거": o.get("근거", ""), "출처": "심사 전에 붙인 정답"}
                for o in _lines(paths.p("generator", "runs", setname, "human-gold.jsonl"))}
        for q in reviews():  # 사람 검토에서 정한 판정이 더 나중 것
            if q["상태"] == "처리" and q["소재"] in cands:
                gold[q["소재"]] = {"판정": q["결정"], "조건": q["조건"], "근거": q["이유"] or "", "출처": "사람 검토 " + q["id"]}
        decs = _lines(os.path.join(latest[setname][1], "decisions.jsonl"))
        items = []
        for dec in decs:
            c = cands.get(dec["id"], {})
            items.append({"id": dec["id"], "유형": c.get("유형"), "채널": c.get("채널"), "제목": c.get("제목"), "자막": c.get("자막") or [],
                          "최종": dec["최종"], "경로": dec.get("경로"), "사유": _reasons(dec), "사람": gold.get(dec["id"])})
        out.append({"회차": setname, "게임": game, "심사_회차": os.path.basename(latest[setname][1]), "소재": items})
    return out


def reviews():
    out = []
    for f in sorted(glob.glob(paths.p("runs", "review", "Q*.json"))):
        q = json.load(open(f, encoding="utf-8"))
        out.append({"id": q["id"], "소재": q["소재"], "출처": q.get("출처"), "AI_판정": q.get("AI_판정"), "AI_이유": q.get("AI_이유"),
                    "상태": q.get("상태"), "결정": q.get("결정"), "조건": q.get("조건") or [], "이유": q.get("이유"),
                    "뒤집음": bool(q.get("뒤집음")), "비싼_오류": bool(q.get("비싼_오류"))})
    return out


def ads(allowed):
    out = []
    for f in sorted(glob.glob(paths.p("runs", "publish", "requests", "*.json"))):
        r = json.load(open(f, encoding="utf-8"))
        post = r.get("글") or {}
        if post.get("게임", "jelly-panic") not in allowed: continue
        pub = r.get("게시") or {}
        # 광고 하나를 대본·심사까지 따라가는 칸(소재·심사_회차)과 다음 할 일을 정하는 칸(공개·내림_이유).
        # 게시 주소는 넣지 않는다: 일부 공개 영상 주소가 공개 화면에 실리면 전체 공개와 같아진다.
        out.append({"id": r["id"], "광고": r["광고"], "채널": r.get("채널"), "제목": post.get("제목"), "글": post.get("글"),
                    "점검": r.get("점검"), "상태": r.get("상태"), "승인됨": bool(r.get("승인")),
                    "소재": r.get("소재"), "심사_회차": r.get("심사_회차"), "요청_때": r.get("요청_때"),
                    "공개": pub.get("공개"), "내림_이유": (r.get("내림") or {}).get("이유")})
    return out


def last_record_time(data):
    """묶음에 들어간 기록 중 가장 늦은 때. 화면은 이 값과 내보낸 때를 같이 보여 준다."""
    ts = [r.get("때") for r in data["심사_이력"]] + [r.get("때") for r in data["회귀"]] + [a.get("요청_때") for a in data["광고"]]
    ts += [l.get("때") for l in _lines(paths.p("runs", "publish", "audit.jsonl"))]
    ts = [t for t in ts if t]
    return max(ts) if ts else None


def build(out_dir=None):
    from . import publish
    out_dir = out_dir or paths.p("board")
    os.makedirs(out_dir, exist_ok=True)
    notes = _load(os.path.join(out_dir, "notes.json")) or {}
    gs = games(); allowed = {k for k, v in gs.items() if v["게시_가능"]}
    kst = datetime.timezone(datetime.timedelta(hours=9))  # 맥·클라우드·CI 어디서 돌려도 한국 시각으로
    data = {"판": FORMAT, "만든_때": datetime.datetime.now(kst).isoformat(timespec="seconds"),
            "게임": [gs[k] for k in sorted(allowed)], "기준표": criteria(),
            "심사_이력": judge_history(notes.get("심사", {}), allowed, set(notes.get("다시_씀", []))), "회귀": regress_history(),
            "생성분": generated(allowed), "사람_검토": reviews(), "광고": ads(allowed),
            "감사": publish.verify_audit()}
    data["심사_품질"] = quality.build(allowed, data["생성분"], set(notes.get("다시_씀", [])), data["사람_검토"])
    data["성과"] = experiment.build([a for a in data["광고"] if a["상태"] != "내림"])
    data["기록_마지막_때"] = last_record_time(data)
    s = json.dumps(data, ensure_ascii=False, indent=1)
    for bad in ("EXPORT_KEY", "TOKEN", "처리자", "누가"):
        assert bad not in s, f"공개용 묶음에 넣으면 안 되는 칸: {bad}"
    open(os.path.join(out_dir, "data.json"), "w", encoding="utf-8").write(s)
    open(os.path.join(out_dir, "data.js"), "w", encoding="utf-8").write("window.ADF_BOARD = " + s + ";\n")
    return {"파일": paths.rel(os.path.join(out_dir, "data.json")), "심사_이력": len(data["심사_이력"]), "회귀": len(data["회귀"]),
            "생성분": sum(len(g["소재"]) for g in data["생성분"]), "사람_검토": len(data["사람_검토"]), "광고": len(data["광고"])}
