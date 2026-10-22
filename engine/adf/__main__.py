"""광고 공장 엔진 명령줄. 앱 화면도 이 명령만 부른다(--json 으로 받음).

  python3 -m adf stages                                   # 단계 목록
  python3 -m adf add 심사.요청문 run=J20 set=dev            # 작업 하나 넣기
  python3 -m adf pipeline 심사 run=J20 set=dev [replay_from=J13]   # 묶음 넣기(앞 작업이 끝나야 다음)
  python3 -m adf run                                      # 대기열 돌리기
  python3 -m adf jobs [--json]                            # 작업 목록
  python3 -m adf show B0003                               # 작업 기록
  python3 -m adf respond B0003 llm-1 응답.txt               # 외부 응답 넣고 이어 가기
  python3 -m adf sync push | sync pull                     # 맥 앱: 요청 올리기 / 응답 받고 이어 돌리기
  python3 -m adf answer                                   # 클라우드 세션: 기다리는 요청에 답하고 올리기
  python3 -m adf review list|stats                         # 사람 검토 대기열
  python3 -m adf review decide Q0001 decision=반려 rules=R1 reason="..."
  python3 -m adf review override run=J12 id=R03-02 decision=반려 rules=R1 reason="..."
"""
import sys, json, shutil, os

from . import jobs, stages, pipelines


def kv(args):
    out = {}
    for a in args:
        k, v = a.split("=", 1)
        try: v = json.loads(v)
        except json.JSONDecodeError: pass
        out[k] = v
    return out


def main(argv):
    as_json = "--json" in argv; argv = [a for a in argv if a != "--json"]
    cmd, rest = (argv[0], argv[1:]) if argv else ("help", [])
    out = None
    if cmd == "stages":
        out = {k: (v.__doc__ or "").strip().split("\n")[0] for k, v in stages.REGISTRY.items()}
    elif cmd == "pipelines":
        out = {k: v["설명"] for k, v in pipelines.PIPELINES.items()}
    elif cmd == "add":
        after = [a.split("=", 1)[1] for a in rest if a.startswith("after=")]
        j = jobs.create(rest[0], kv([a for a in rest[1:] if not a.startswith("after=")]), after=after)
        out = j.d
    elif cmd == "pipeline":
        out = [j.d for j in pipelines.enqueue(rest[0], kv(rest[1:]))]
    elif cmd == "run":
        n = jobs.run_queue()
        out = {"돌린_작업": n, "상태": summary()}
    elif cmd == "jobs":
        out = [{k: j.d[k] for k in ("id", "단계", "묶음", "상태", "모델", "걸린_초", "결과", "오류")} | {"달러": (j.d["비용"] or {}).get("달러")} for j in jobs.all_jobs()]
    elif cmd == "show":
        out = jobs.get(rest[0]).d
    elif cmd == "respond":
        j = jobs.get(rest[0]); shutil.copy(rest[2], os.path.join(j.dir, f"response-{rest[1]}.txt"))
        j.d["상태"] = "대기"; j.save(); j.log(f"응답 받음: {rest[1]}"); out = j.d
    elif cmd == "review":
        from . import review
        sub = rest[0] if rest else "list"; a = kv([x for x in rest[1:] if "=" in x])
        if sub == "list": out = review.items(a.get("state"))
        elif sub == "stats": out = review.stats()
        elif sub == "decide": out = review.decide(rest[1], a["decision"], a.get("reason", ""), [r for r in str(a.get("rules", "")).split(",") if r], a.get("who", "작가"))
        elif sub == "override": out = review.override(a["run"], a["id"], a["decision"], a.get("reason", ""), [r for r in str(a.get("rules", "")).split(",") if r], a.get("who", "작가"))
    elif cmd == "regress":
        from . import regress
        sub = rest[0] if rest else "status"; a = kv(rest[1:])
        if sub == "check": out = regress.check(provider=a.get("provider"), release=bool(a.get("release")), force=bool(a.get("force")))
        elif sub == "status": out = regress.collect()
        elif sub == "baseline": out = regress.baseline(a["run"], a.get("factsheet"), a.get("note", ""))
    elif cmd == "publish":
        from . import publish
        sub = rest[0] if rest else "list"; a = kv(rest[1:])
        if sub == "request": out = publish.request(a["ad"], channel=a.get("channel"))
        elif sub == "withdraw": out = publish.withdraw(a["id"], a.get("why", ""))
        elif sub == "public": out = publish.make_public(a["id"], a.get("who"))
        elif sub == "approve": out = publish.approve(a["id"], a.get("who"), a.get("note", ""))
        elif sub == "run": out = publish.run(a["id"])
        elif sub == "audit": out = publish.verify_audit()
        else: out = publish.requests()
    elif cmd == "export":
        from . import export
        out = export.build(kv(rest).get("out"))
    elif cmd == "dashboard":
        from . import regress, review, publish, factcheck, paths as P
        import glob as G
        js = jobs.all_jobs()
        cost = {"입력_토큰": 0, "출력_토큰": 0, "추정_포함": False, "달러": 0.0, "달러_모름": 0}
        for j in js:
            c = j.d.get("비용") or {}
            cost["입력_토큰"] += c.get("입력_토큰", 0); cost["출력_토큰"] += c.get("출력_토큰", 0)
            cost["추정_포함"] |= bool(c.get("추정_포함"))
            cost["구독_환산_달러"] = round(cost.get("구독_환산_달러", 0) + (c.get("구독_환산_달러") or 0), 4)
            if c.get("호출"):
                if c.get("달러") is None: cost["달러_모름"] += 1
                else: cost["달러"] += c["달러"]
        facts = {}
        for ad in G.glob(P.p("adapters", "*", "adapter.json")):
            m = json.load(open(ad, encoding="utf-8"))
            if "자동_대조" in m:
                r, _ = factcheck.compare(os.path.dirname(ad), P.p(m["사실표"]["파일"]))
                facts[m["id"]] = {"이름": m["이름"], "결론": r["결론"], "어긋남": r["어긋남"], "사실표_판": r["사실표_판"], "게시": m.get("광고_게시")}
        out = {"작업": summary(), "최근_작업": [{k: j.d[k] for k in ("id", "단계", "묶음", "상태", "모델", "제공자", "걸린_초", "결과", "오류", "만든_때")} | {"달러": (j.d["비용"] or {}).get("달러"), "토큰": [(j.d["비용"] or {}).get("입력_토큰"), (j.d["비용"] or {}).get("출력_토큰")], "추정": (j.d["비용"] or {}).get("추정_포함"), "응답_대기": sorted(os.path.basename(x) for x in G.glob(os.path.join(j.dir, "request-*.md")) if not os.path.exists(x.replace("request-", "response-").replace(".md", ".txt")))} for j in js[-60:]][::-1],
               "비용": cost, "회귀": regress.collect()["회차"], "검토": {"통계": review.stats(), "대기": review.items("대기"), "처리": review.items("처리")[-20:]},
               "게시": publish.requests(), "감사": publish.verify_audit(), "사실표": facts}
    elif cmd == "plan":
        from . import plan
        a = kv(rest[1:]); j = jobs.get(a["job"]); spec = json.load(open(os.path.join(j.dir, "spec.json"), encoding="utf-8"))
        chk = plan.check(spec["명세"], spec["요청"])
        if not chk["진행"]: raise SystemExit("명세 검사를 통과하지 못해 넣지 않았습니다: " + " / ".join(chk["문제"] + chk["물어볼_것"]))
        out = {"넣은_작업": plan.enqueue(spec["명세"], a["run"])}
    elif cmd == "answer":
        from . import relay
        a = kv(rest)
        if a.get("pull", True): relay.pull()
        done = relay.answer(int(a.get("limit", 50)))
        out = {"응답": done, "남은_요청": len(relay.pending())}
        if done and a.get("push", True): out["올림"] = relay.push(f"AI 응답 {len(done)}건 (클라우드 세션)")
    elif cmd == "sync":
        from . import relay
        sub = rest[0] if rest else "pull"
        if sub == "push":
            out = {**relay.push("맥 앱: 작업 상태와 AI 요청"), "기다리는_요청": len(relay.pending())}
        else:
            out = relay.pull(); out["대기열"] = jobs.run_queue(); out["상태"] = summary()
    elif cmd == "youtube":
        from . import youtube
        sub = rest[0] if rest else "status"; a = kv(rest[1:])
        if sub == "client": out = youtube.set_client(a["file"])
        elif sub == "auth-url": out = youtube.auth_url()
        elif sub == "auth-code": out = youtube.auth_code(a["url"])
        elif sub == "channel": out = youtube.channel()
        else: out = {"권한": youtube.ready(), "열쇠_파일": youtube.cred_path(), "채널_id": youtube.load().get("channel_id")}
    elif cmd == "retry":
        j = jobs.get(rest[0]); j.d.update({"상태": "대기", "오류": None}); j.save(); out = j.d
    else:
        print(__doc__); return
    if as_json:
        print(json.dumps(out, ensure_ascii=False))
    elif isinstance(out, list):
        for o in out: print(json.dumps(o, ensure_ascii=False))
    else:
        print(json.dumps(out, ensure_ascii=False, indent=1))


def summary():
    c = {}
    for j in jobs.all_jobs(): c[j.d["상태"]] = c.get(j.d["상태"], 0) + 1
    return c


if __name__ == "__main__":
    main(sys.argv[1:])
