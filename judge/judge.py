"""광고 소재 심사기. 설계 = DESIGN.md

  python3 judge.py prompt  --run J01 --set dev           # ① 규칙 검사 + ② AI 판정 요청문 만들기
  (AI 판정 결과를 runs/J01/llm-1.jsonl, llm-2.jsonl 로 저장. API 키가 있으면 api 로)
  python3 judge.py api     --run J01 --times 2
  python3 judge.py combine --run J01                     # 세 층 합쳐 최종 판정 → decisions.jsonl
  python3 judge.py score   --run J01                     # 정답과 대조 (평가셋일 때만) → score.json
--set 은 dev · holdout · 생성 회차 이름(R01 등).
--game 을 안 주면 생성 회차는 그 회차 run.json 의 게임, 평가셋은 젤리 패닉.
"""
import argparse, json, os, re, sys, glob, datetime, collections

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
PROMPT_VER = "judge-v1"
GOLD_KEYS = {"정답", "걸린것", "경계", "메모", "나눔"}
VIDEO_KINDS = {"영상", None}

def load(path): return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]

def load_set(name):
    if name == "dev": return load(os.path.join(ROOT, "eval", "dev.jsonl"))
    if name == "holdout": return load(os.path.join(ROOT, "eval", "holdout", "holdout.jsonl"))
    if name == "holdout2": return load(os.path.join(ROOT, "eval", "holdout2", "holdout2.jsonl"))  # 2026-10-22 새 숨긴 묶음(따로 만든 세션이 작성)
    if name == "review": return load(os.path.join(ROOT, "eval", "review", "review.jsonl"))  # 사람 검토에서 꼬리표 붙여 넘어온 소재
    return load(os.path.join(ROOT, "generator", "runs", name, "candidates.jsonl"))

def set_game(name):
    p = os.path.join(ROOT, "generator", "runs", name, "run.json")
    if name not in ("dev", "holdout", "holdout2", "review") and os.path.exists(p):
        return json.load(open(p, encoding="utf-8")).get("game") or "jelly-panic"
    return "jelly-panic"

def criteria_version():
    md = open(os.path.join(ROOT, "CRITERIA.md"), encoding="utf-8").read()
    dates = re.findall(r"^- (\d{4}-\d{2}-\d{2})", md.split("## 변경 기록")[-1], re.M)
    return f"{dates[-1]}#{len(dates)}" if dates else "unknown"

def cuts_text(c):
    out = []
    for k in c.get("컷") or []:
        out.append(k["장면"] if isinstance(k, dict) else str(k))
    return out

def is_video(c): return c.get("종류", "영상") == "영상"

# ── ① 규칙 검사: 확실한 것만. 애매하면 AI 판정으로 넘긴다 ──
def rules(c, name="젤리 패닉"):
    hits = []
    copy = " ".join((c.get("자막") or []) + [c.get("끝") or "", c.get("제목") or "", c.get("문구") or ""])
    copy = re.sub(r"https?://\S+", " ", copy)  # 링크 주소 속 숫자는 문구가 아님(J07에서 12개 모두 오탐, 이후 고침)
    scene = " ".join([c.get("첫컷") or ""] + cuts_text(c))
    if re.search(r"1위|전국|평점|최고의|1등|일등", copy): hits.append(("R2", "근거 없는 순위·평점 표현이 문구에 있습니다. 지우세요."))
    if re.search(r"상품권|현금|추첨|경품|상금|아이템 지급|보상 지급", copy): hits.append(("R4", "경품·보상 문구가 있습니다. 보상 문구를 지우세요."))
    rating = r"이용가|등급" if name == "젤리 패닉" else r"이용가|이용\s*등급|(전체|청소년|\d+\s*세)\s*등급|등급\s*(분류|판정|받)"  # 보석 「등급」은 게임 안 낱말(JG01 오탐 2건 뒤 고침)
    if re.search(rating, copy): hits.append(("R5", "받은 등급이 없어 등급 표시를 쓸 수 없습니다. 지우세요."))
    if re.search(r"\d", copy) and not any(h[0] in ("R2", "R4", "R5") for h in hits): hits.append(("G8", "문구에 숫자가 있습니다. 숫자 없이 장면으로 쓰세요."))
    if name == "젤리 패닉" and re.search(r"같은\s*판(으로|이|에서)?\s*(바로\s*)?열", copy) and "seed=" not in (c.get("링크") or ""):
        hits.append(("R1", "같은 판으로 열린다는 문구가 있는데 링크에 판 번호(seed)가 없습니다. 공유 버튼은 그림만 보냅니다. 문구를 지우거나 링크에 ?seed=번호를 붙이세요."))  # G002 dev P15 를 모델 두 번이 모두 통과시켜 기계 규칙으로 옮김
    if name == "젤리 패닉" and re.search(r"보스|병사|핀을? 뽑|(^|\s)용(이|을|과|\s)", scene + " ".join(c.get("도입부") or [])): hits.append(("R1", "게임에 없는 것(보스·병사·핀 뽑기·용)이 나옵니다. 실제 위협 장면으로 바꾸세요."))
    if is_video(c):
        if c.get("화면비") and c["화면비"] != "9:16": hits.append(("G6", "세로 9:16이 아닙니다. 세로로 다시 자르세요."))
        if not c.get("자막"): hits.append(("G4", "자막이 없습니다. 장면마다 자막을 넣으세요."))
        sec = c.get("게임이름_처음_나오는_초", "자막")
        early = any(name in s for s in (c.get("자막") or [])[:2]) or name in (c.get("제목") or "")
        if (sec == "자막" and not early) or (sec != "자막" and (sec is None or sec > 5)): hits.append(("G3", "게임 이름이 앞쪽에 없습니다. 첫 자막에 넣으세요."))
        if not c.get("끝") or not c.get("링크"): hits.append(("G5", "끝에 할 일이나 출처 태그 링크가 없습니다. 하나 넣으세요."))
        elif re.search(r"(하고|누르고).*(하고|까지)", c["끝"]): hits.append(("G5", "끝에 할 일이 여럿입니다. 하나만 남기세요."))
        if c.get("도입부") is not None and c.get("유형", "").startswith("세계관"):
            if len(c["도입부"]) > 4: hits.append(("R1", "세계관 그림이 4장을 넘습니다. 4장 이내로 줄이세요."))
            if "실제 게임 화면" not in (c.get("넘어가는_표시") or ""): hits.append(("R1", "실제 게임 화면으로 넘어가는 표시가 없습니다. 페이지 넘김과 「실제 게임 화면」 자막을 넣으세요."))
    return hits

def blind(c):
    b = {k: v for k, v in c.items() if k not in GOLD_KEYS and k not in ("형식_문제", "출처", "링크", "채널")}
    b["링크"] = "있음(출처 태그)" if c.get("링크") else "없음"
    if isinstance((c.get("컷") or [None])[0], dict): b["컷"] = cuts_text(c)
    return {k: v for k, v in b.items() if v not in (None, [], "")}

def prompt(run, setname, game=None):
    items = load_set(setname); game = game or set_game(setname)
    facts = json.load(open(os.path.join(ROOT, "game", f"{game}.json"), encoding="utf-8"))
    name = facts.get("짧은이름") or game
    md = open(os.path.join(ROOT, "CRITERIA.md"), encoding="utf-8").read()
    rubric = md[md.index("## 1. 광고에 넣을 것"):md.index("## 4. 평가셋")]
    tmpl = open(os.path.join(HERE, "prompts", PROMPT_VER + ".md"), encoding="utf-8").read()
    if game != "jelly-panic":  # 틀은 젤리 패닉 기준으로 쓰여 있어 게임 이름만 바꾸고, 예시 칸 안내를 붙인다
        tmpl = tmpl.replace("젤리 패닉", name).replace("## 판정하는 법", "## 이 게임에서 보는 법\n기준표 1-1 표의 「젤리 패닉 장면」 칸은 젤리 패닉 예시다. 이 게임은 사실표에서 같은 성격의 장면인지로 본다. 사실표의 「광고에_쓰지_않는_것」이 화면에 있으면 R1로 반려한다.\n\n## 판정하는 법")
    rows = "\n".join(json.dumps(blind(c), ensure_ascii=False) for c in items)
    p = tmpl.replace("{{FACTS}}", json.dumps({k: v for k, v in facts.items() if k not in ("근거", "링크")}, ensure_ascii=False)).replace("{{RUBRIC}}", rubric).replace("{{ITEMS}}", rows)
    d = os.path.join(HERE, "runs", run); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "prompt.md"), "w", encoding="utf-8").write(p)
    with open(os.path.join(d, "rules.jsonl"), "w", encoding="utf-8") as f:
        for c in items: f.write(json.dumps({"id": c["id"], "걸림": rules(c, name)}, ensure_ascii=False) + "\n")
    json.dump({"run": run, "set": setname, "게임": game, "기준표_판": criteria_version(), "요청문_판": PROMPT_VER, "모델": None, "판정_횟수": None,
               "만든_때": datetime.datetime.now().isoformat(timespec="seconds"), "소재_수": len(items)},
              open(os.path.join(d, "run.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(os.path.join(d, "prompt.md"), len(p), "자 ·", len(items), "개")

def api(run, times, model):
    if not os.environ.get("ANTHROPIC_API_KEY"): sys.exit("ANTHROPIC_API_KEY 없음: Claude 세션이 prompt.md 로 llm-1.jsonl·llm-2.jsonl 을 만든다.")
    import anthropic
    d = os.path.join(HERE, "runs", run); p = open(os.path.join(d, "prompt.md"), encoding="utf-8").read()
    cl = anthropic.Anthropic()
    for i in range(1, times + 1):
        m = cl.messages.create(model=model, max_tokens=16000, messages=[{"role": "user", "content": p}])
        open(os.path.join(d, f"llm-{i}.jsonl"), "w", encoding="utf-8").write("".join(b.text for b in m.content if b.type == "text"))

def parse_llm(path):
    out = {}
    for l in open(path, encoding="utf-8"):
        l = l.strip()
        if not l.startswith("{"): continue
        try: r = json.loads(l)
        except json.JSONDecodeError: continue
        v = r.get("위반") or []
        verdict = "사람 확인" if r.get("사람확인") else ("반려" if v else "통과")
        out[r["id"]] = {"판정": verdict, "위반": v, "사람확인_이유": r.get("사람확인_이유", "")}
    return out

def combine(run):
    d = os.path.join(HERE, "runs", run)
    rl = {r["id"]: r["걸림"] for r in load(os.path.join(d, "rules.jsonl"))}
    llms = [parse_llm(p) for p in sorted(glob.glob(os.path.join(d, "llm-*.jsonl")))]
    meta = json.load(open(os.path.join(d, "run.json"), encoding="utf-8"))
    out = []
    for cid, hits in rl.items():
        votes = [m.get(cid) for m in llms if m.get(cid)]
        if hits:
            final, how = "반려", "① 규칙"
            reasons = [{"조건": r, "사유": s, "출처": "규칙"} for r, s in hits]
        elif not votes:
            final, how, reasons = "사람 확인", "AI 판정 없음", []
        else:
            vs = {v["판정"] for v in votes}
            if "사람 확인" in vs: final, how = "사람 확인", "③ AI가 사람 확인 요청"
            elif len(vs) > 1: final, how = "사람 확인", "③ 두 판정 엇갈림"
            else: final, how = vs.pop(), "② AI 판정 일치"
            reasons = [dict(x, 출처=f"AI {i+1}회") for i, v in enumerate(votes) for x in v["위반"]]
            reasons += [{"사람확인_이유": v["사람확인_이유"], "출처": f"AI {i+1}회"} for i, v in enumerate(votes) if v["사람확인_이유"]]
        out.append({"id": cid, "최종": final, "경로": how, "근거": reasons,
                    "AI_판정": [v["판정"] for v in votes], "기준표_판": meta["기준표_판"], "요청문_판": meta["요청문_판"], "모델": meta.get("모델")})
    with open(os.path.join(d, "decisions.jsonl"), "w", encoding="utf-8") as f:
        for o in out: f.write(json.dumps(o, ensure_ascii=False) + "\n")
    c = collections.Counter(o["최종"] for o in out); p = collections.Counter(o["경로"] for o in out)
    print("최종:", dict(c), "· 경로:", dict(p))

def kappa(pairs, labels):
    n = len(pairs); po = sum(a == b for a, b in pairs) / n
    pe = sum((sum(a == l for a, _ in pairs) / n) * (sum(b == l for _, b in pairs) / n) for l in labels)
    return round((po - pe) / (1 - pe), 3) if pe < 1 else 1.0

def score(run):
    d = os.path.join(HERE, "runs", run); meta = json.load(open(os.path.join(d, "run.json"), encoding="utf-8"))
    gold = {c["id"]: c for c in load_set(meta["set"])}
    hg = os.path.join(ROOT, "generator", "runs", meta["set"], "human-gold.jsonl")
    if os.path.exists(hg):  # 생성분: 심사기를 돌리기 전에 사람이 붙인 정답
        for o in load(hg): gold[o["id"]] = {**gold[o["id"]], "정답": o["정답"], "걸린것": o["걸린것"]}
    dec = {o["id"]: o for o in load(os.path.join(d, "decisions.jsonl"))}
    L = ["통과", "반려", "사람 확인"]
    pairs = [(gold[i]["정답"], dec[i]["최종"]) for i in gold]
    conf = {g: {p: sum(1 for a, b in pairs if a == g and b == p) for p in L} for g in L}
    rej = [i for i in gold if gold[i]["정답"] == "반려"]
    caught = [i for i in rej if dec[i]["최종"] in ("반려", "사람 확인")]
    pred_rej = [i for i in gold if dec[i]["최종"] == "반려"]
    per_rule = {}
    for i in rej:
        for r in gold[i]["걸린것"]:
            per_rule.setdefault(r, [0, 0]); per_rule[r][1] += 1
            if dec[i]["최종"] in ("반려", "사람 확인"): per_rule[r][0] += 1
    rep = {
        "회차": run, "묶음": meta["set"], "기준표_판": meta["기준표_판"], "요청문_판": meta["요청문_판"], "모델": meta.get("모델"), "판정_횟수": meta.get("판정_횟수"),
        "소재_수": len(pairs),
        "판정_일치": round(sum(a == b for a, b in pairs) / len(pairs), 3),
        "반려_재현율": round(len(caught) / len(rej), 3) if rej else None,
        "반려_정밀도": round(sum(1 for i in pred_rej if gold[i]["정답"] == "반려") / len(pred_rej), 3) if pred_rej else None,
        "사람_확인_비율": round(sum(1 for _, b in pairs if b == "사람 확인") / len(pairs), 3),
        "카파": kappa(pairs, L),
        "혼동표(정답→판정)": conf,
        "조건별_재현": {r: f"{a}/{b}" for r, (a, b) in sorted(per_rule.items())},
        "비싼_오류(반려를_통과시킴)": [i for i in rej if dec[i]["최종"] == "통과"],
        "통과를_반려함": [i for i in gold if gold[i]["정답"] == "통과" and dec[i]["최종"] == "반려"],
        "통과인데_사람확인": [i for i in gold if gold[i]["정답"] == "통과" and dec[i]["최종"] == "사람 확인"],
        "경로별": dict(collections.Counter(dec[i]["경로"] for i in gold)),
    }
    json.dump(rep, open(os.path.join(d, "score.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(rep, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["prompt", "api", "combine", "score"])
    ap.add_argument("--run", required=True); ap.add_argument("--set", default="dev")
    ap.add_argument("--game", default=None); ap.add_argument("--times", type=int, default=2); ap.add_argument("--model", default="claude-sonnet-5-5")
    a = ap.parse_args()
    {"prompt": lambda: prompt(a.run, a.set, a.game), "api": lambda: api(a.run, a.times, a.model),
     "combine": lambda: combine(a.run), "score": lambda: score(a.run)}[a.cmd]()
