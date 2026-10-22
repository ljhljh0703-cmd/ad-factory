"""광고 소재 생성기.

쓰는 법
  python3 generate.py build  --run R01 --per-type 2   # AI에 줄 요청문 만들기 (runs/R01/prompt.md)
  python3 generate.py build  --run G01 --game gem-tower   # 다른 게임: game/<게임>.json 사실표를 읽음
  python3 generate.py api    --run R01                # ANTHROPIC_API_KEY 가 있으면 바로 호출해 raw.jsonl 저장
  python3 generate.py ingest --run R01                # AI 결과(raw.jsonl)를 받아 형식 검사 → candidates.jsonl
  python3 generate.py template --run T01              # AI 없이 사실표 조합으로 만든 기준선 (비교용)

API 키가 없으면 Claude 세션이 prompt.md 를 그대로 받아 raw.jsonl 을 만든다. 결과는 같은 ingest 를 거친다.
"""
import argparse, json, os, re, sys, itertools, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_GAME = "jelly-panic"
FACTS = os.path.join(ROOT, "game", DEFAULT_GAME + ".json")  # 예전 호출 호환(기본 게임)
CRITERIA = os.path.join(ROOT, "CRITERIA.md")
TYPES = ["질 뻔하다 뒤집기", "열린 끝", "선택 순간", "손 화면·반응", "같은 판 도전", "답답한 플레이", "세계관 도입 → 실제 플레이"]  # 답답한 플레이 = 기준표 1-1 작가 결정 10-22(생성기에 빠져 있던 것 10-22 추가)
WORLD = TYPES[-1]
CHANNELS = {"reels": "인스타그램 릴스", "tiktok": "틱톡", "shorts": "유튜브 쇼츠"}
LOSE_TYPES = {"열린 끝", "같은 판 도전", "답답한 플레이"}

def facts_path(game=DEFAULT_GAME):
    p = os.path.join(ROOT, "game", f"{game}.json")
    if not os.path.exists(p): sys.exit(f"사실표 없음: game/{game}.json")
    return p

def load_facts(game=DEFAULT_GAME): return json.load(open(facts_path(game), encoding="utf-8"))

def types_for(facts):
    """세계관 도입은 사실표에 광고_세계관이 있는 게임만(작가가 정한 광고 세계관이 없으면 지어내지 않음)."""
    return TYPES if facts.get("광고_세계관") else TYPES[:-1]

def game_terms(facts):
    """컷 근거로 인정할 게임 안 이름: 이름 붙은 목록 + 보석 이름 + 앞부분·뒤에 나오는 것."""
    keyed = [k for k in ("위협", "아이템", "지키는것") if k in facts]
    if keyed:  # 젤리 패닉 꼴 사실표: 예전 검사와 같게(R01·R02 형식 결과를 바꾸지 않음)
        return {x["이름"] for k in keyed for x in facts[k]}
    names = set()
    for v in facts.values():
        if isinstance(v, list):
            names |= {x["이름"] for x in v if isinstance(x, dict) and x.get("이름")}
    gem = facts.get("보석")
    if isinstance(gem, dict): names |= set(gem.get("확인한_이름") or [])
    for k in ("앞부분에_나오는_것", "조금_뒤에_나오는_것"):
        names |= {re.split(r"[(·]|\s\d", x)[0].strip() for x in facts.get(k) or [] if isinstance(x, str)}
    return {n for n in names if n}

def posting(facts):
    """게시 막힘이면 그 메모, 아니면 None."""
    v = facts.get("광고_게시")
    if isinstance(v, dict): return None if v.get("가능", True) else (v.get("메모") or "게시 불가")
    if isinstance(v, str) and re.search(r"않음|불가|금지", v): return v
    return None

def obj(word):
    """목적격 조사: 받침 있으면 을, 없으면 를."""
    ch = word[-1]
    return ("을" if "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 else "를")

def run_game(run):
    p = os.path.join(HERE, "runs", run, "run.json")
    return (json.load(open(p, encoding="utf-8")).get("game") if os.path.exists(p) else None) or DEFAULT_GAME

def run_dir(run):
    d = os.path.join(HERE, "runs", run); os.makedirs(d, exist_ok=True); return d

def section(md, start, end):
    a = md.index(start); b = md.index(end, a); return md[a:b].strip()

# ── 요청문 ──
def build(run, per_type, game=DEFAULT_GAME):
    facts = load_facts(game); name = facts.get("짧은이름") or game
    types = types_for(facts); world = WORLD in types
    md = open(CRITERIA, encoding="utf-8").read()
    put = section(md, "## 1. 광고에 넣을 것", "## 2. 통과 조건")
    gates = section(md, "## 2. 통과 조건", "### 판정 메모")
    schema = {
        "유형": "|".join(types), "채널": "reels|tiktok|shorts", "제목": "게시물 제목 한 줄",
        "첫컷": "첫 컷 설명", "도입부": ["세계관 유형만: 그림책 그림 설명, 4장 이내"],
        "넘어가는_표시": "세계관 유형만: 예) 페이지 넘김 + 「실제 게임 화면」 자막",
        "컷": [{"장면": "무엇이 보이나", "게임_근거": "사실표의 위협·아이템·모드·화면 이름 중 하나 이상, 도입부 그림은 '광고 세계관'"}],
        "자막": ["화면에 뜨는 글자, 첫 줄에 「젤리 패닉」 포함"], "소리": "효과음·반응 소리",
        "끝": "할 일 한 가지", "녹화_메모": "작가가 실제로 녹화해야 할 판 상황",
        "그림_요청문": ["세계관 유형만: 웹 ChatGPT에 넣을 그림책 그림 요청문, 장마다 하나"]
    }
    world_rule = "\n- 세계관 유형은 1-4 조건을 지키고, 그림_요청문은 그림책 그림체(부드러운 색연필·수채 느낌)로 게임 화면과 다르게 요청한다. 아기 쿠키·도둑까마귀·시럽·균열 생김새는 「게임 속 모습과 같은 색과 모양」이라고 적는다. 글자는 그림에 넣지 않는다."
    extra = ""
    if game != DEFAULT_GAME:
        schema["컷"][0]["게임_근거"] = "사실표에 있는 이름(조작·모드·화면·보석·위협 등) 중 하나 이상"
        schema["자막"] = [f"화면에 뜨는 글자, 첫 줄에 「{name}」 포함"]
        if not world:
            for k in ("도입부", "넘어가는_표시", "그림_요청문"): schema.pop(k)
            world_rule = ""
        extra = ("\n- 기준표 1-1 표의 「젤리 패닉 장면」 칸은 젤리 패닉 예시다. 이 게임에서는 사실표에서 같은 성격의 장면(위기, 선택, 뒤집기)을 찾아 쓴다."
                 "\n- 기준표 1-2 「지켜야 할 것이 보이기」는 이 게임에서 지키는 대상(라이프·광산처럼 사실표에 있는 것)이 첫 실제 컷에 보이는지로 본다."
                 "\n- 사실표의 「광고에_쓰지_않는_것」은 화면에 넣지 않는다.")
        if not world: extra += "\n- 이 게임은 광고 세계관이 정해지지 않았다. 게임에 없는 이야기·인물을 지어 넣지 않는다."
        if posting(facts): extra += f"\n- 게시 막힘: {posting(facts)}. 내부 시험용 대본으로만 쓴다."
    p = f"""너는 젤리 패닉 무료 SNS 숏폼 광고 대본을 쓰는 사람이다.
유형마다 {per_type}개씩, 모두 {per_type*len(types)}개를 만든다. 채널은 릴스·틱톡·쇼츠를 고르게 섞는다.

## 게임 사실표 (여기 있는 것만 화면에 쓴다)
```json
{json.dumps(facts, ensure_ascii=False, indent=1)}
```

## 기준표 1절 (광고에 넣을 것)
{put}

## 기준표 2·3절 (통과 조건과 반려 조건)
{gates}

## 쓰는 규칙
- 컷마다 「게임_근거」를 채운다. 사실표의 「없는_것」은 쓰지 않는다. 「조금_뒤에_나오는_것」을 쓰면 녹화_메모에 몇 단계 장면인지 적는다.
- 자막 첫 줄 또는 두 번째 줄 안에 「젤리 패닉」을 넣는다.
- 숫자·순위·평점·시험 결과를 쓰지 않는다. 「한 칸」「한 수」 같은 장면 묘사는 된다.
- 운영자 계정 목소리로 쓴다. 지어낸 사용자 후기, AI 실사 인물, 유명 음원은 쓰지 않는다.{world_rule}
- 같은 유형 안에서도 첫 3초 후킹(패턴 깨기·질문·공감 상황)과 쓰는 위협을 서로 다르게 고른다.{extra}

## 출력
한 줄에 하나, JSON Lines만. 설명 없이. 형식:
{json.dumps(schema, ensure_ascii=False)}
"""
    if game != DEFAULT_GAME:
        head, tail = p.split("## 게임 사실표", 1)
        rules_part = tail[tail.index("## 쓰는 규칙"):]
        tail = tail[:tail.index("## 쓰는 규칙")]
        p = head.replace("젤리 패닉", name) + "## 게임 사실표" + tail + rules_part.replace("「젤리 패닉」을", f"「{name}」" + obj(name)).replace("「젤리 패닉」", f"「{name}」").replace("쓰는 위협을", "쓰는 장면을")
    d = run_dir(run)
    open(os.path.join(d, "prompt.md"), "w", encoding="utf-8").write(p)
    json.dump({"run": run, "per_type": per_type, "made": datetime.datetime.now().isoformat(timespec="seconds"),
               "facts": os.path.relpath(facts_path(game), ROOT), "criteria": os.path.relpath(CRITERIA, ROOT), "game": game},
              open(os.path.join(d, "run.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(os.path.join(d, "prompt.md"), len(p), "자")

# ── API 호출 (키가 있을 때) ──
def api(run, model):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        sys.exit("ANTHROPIC_API_KEY 없음: Claude 세션이 prompt.md 로 raw.jsonl 을 만들고 ingest 를 돌린다.")
    import anthropic
    d = run_dir(run); prompt = open(os.path.join(d, "prompt.md"), encoding="utf-8").read()
    msg = anthropic.Anthropic().messages.create(model=model, max_tokens=16000, messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    open(os.path.join(d, "raw.jsonl"), "w", encoding="utf-8").write(text)
    print("raw.jsonl 저장")

# ── 받기와 형식 검사 ──
def check(c, facts):
    probs = []
    name = facts.get("짧은이름") or "젤리 패닉"
    names = game_terms(facts)
    if c.get("유형") not in types_for(facts): probs.append("유형 이름이 1-1에 없음" if c.get("유형") not in TYPES else "이 게임은 광고 세계관이 없어 세계관 유형을 쓸 수 없음")
    subs = c.get("자막") or []
    if not subs: probs.append("G4 자막 없음")
    if not any(name in s for s in subs[:2]) and name not in c.get("제목", ""): probs.append("G3 앞쪽에 게임 이름 없음")
    if not c.get("끝") or re.search(r"(하고|누르고).*(하고|까지)", c.get("끝", "")): probs.append("G5 끝 할 일이 없거나 여럿")
    text = " ".join(subs + [c.get("끝", ""), c.get("제목", "")])
    text = re.sub(r"https?://\S+", " ", text)  # 링크 주소 속 숫자는 문구가 아님(R02에서 오탐)
    if re.search(r"\d|(백|천|만)\s*명|평점|최고|최초|일등|일위", text): probs.append("G8·R2 숫자·순위 표현 의심")
    banned = facts["없는_것"]
    allcut = json.dumps(c.get("컷", []), ensure_ascii=False) + c.get("첫컷", "")
    for b in banned:
        hit = re.search(r"(^|[\s,.「(\"])" + re.escape(b) + r"(이|가|을|를|과|와|의|\s|,|$)", allcut) if len(b) == 1 else (b in allcut)  # 한 글자 낱말은 단어 경계로(「광고용」 오탐)
        if hit and not (c.get("유형") == WORLD and b == "마을"): probs.append(f"R1 사실표에 없는 것: {b}")
    for k in c.get("컷", []):
        if not k.get("게임_근거"): probs.append("G1 컷 근거 칸 빔")
    if c.get("유형") == WORLD and WORLD in types_for(facts):
        intro = c.get("도입부") or []
        if not intro or len(intro) > 4: probs.append("1-4 도입부 0장 또는 4장 초과")
        if not c.get("넘어가는_표시") or "실제 게임 화면" not in c.get("넘어가는_표시", ""): probs.append("1-4 넘어가는 표시 없음")
        if len(c.get("그림_요청문") or []) != len(intro): probs.append("1-4 그림 요청문 수가 도입부와 다름")
        for b in ["용", "보스", "병사", "인간"]:
            if any(b in x for x in intro): probs.append(f"1-4 도입부에 게임에 없는 것: {b}")
        real = [k for k in (c.get("컷") or []) if "광고 세계관" not in k.get("게임_근거", "")]
        if not real or not any(n in json.dumps(real[0], ensure_ascii=False) for n in names): probs.append("G2 넘어간 뒤 첫 실제 컷에 위기 없음")
    return probs

def ingest(run):
    game = run_game(run); facts = load_facts(game); block = posting(facts)
    d = run_dir(run); raw = os.path.join(d, "raw.jsonl")
    rows, bad = [], 0
    for n, line in enumerate(open(raw, encoding="utf-8"), 1):
        line = line.strip()
        if not line or line.startswith("```"): continue
        try: rows.append(json.loads(line))
        except json.JSONDecodeError: bad += 1
    out = []
    for i, c in enumerate(rows, 1):
        ch = c.get("채널", "reels"); c["id"] = f"{run}-{i:02d}"
        c["채널"] = CHANNELS.get(ch, ch); c["화면비"] = "9:16"
        c["링크"] = f'{facts["링크"]}?src={ch}&ad={c["id"]}'
        c["형식_문제"] = check(c, facts); c["출처"] = "AI 생성"; c["게임"] = game
        if block: c["게시"] = f"막힘: {block}"
        out.append(c)
    with open(os.path.join(d, "candidates.jsonl"), "w", encoding="utf-8") as f:
        for c in out: f.write(json.dumps(c, ensure_ascii=False) + "\n")
    ok = sum(1 for c in out if not c["형식_문제"])
    by = {t: sum(1 for c in out if c.get("유형") == t) for t in types_for(facts)}
    rep = {"run": run, "게임": game, "받은 줄": len(rows), "읽기 실패": bad, "형식 통과": ok, "형식 문제": len(out) - ok, "유형별": by,
           "문제 목록": {c["id"]: c["형식_문제"] for c in out if c["형식_문제"]}}
    json.dump(rep, open(os.path.join(d, "ingest-report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(rep, ensure_ascii=False, indent=1))

# ── AI 없이 조합으로 만드는 기준선 ──
def template(run, game=DEFAULT_GAME):
    if game != DEFAULT_GAME: sys.exit("조합 기준선은 젤리 패닉 위협 목록으로만 만든다(비교용)")
    facts = load_facts(game)
    hooks = ["여기서 살 수 있음?", "끝났다 싶었는데", "출근길 한 판"]
    early = [t for t in facts["위협"] if t["이름"] != "도둑까마귀"]
    out = []
    for i, (t, h) in enumerate(itertools.product(early, hooks), 1):
        out.append({"유형": "질 뻔하다 뒤집기", "채널": list(CHANNELS)[i % 3], "제목": f"젤리 패닉 · {t['이름']} 막기",
                    "첫컷": f"{t['이름']} 예고 카운트다운, 소중한 것 바로 옆", "컷": [{"장면": "조각 끌어 예고 칸 덮기", "게임_근거": t["이름"]}, {"장면": "줄이 연달아 터짐 + 효과음", "게임_근거": "연쇄"}],
                    "자막": ["젤리 패닉", h, "막았다"], "소리": "연쇄 효과음", "끝": "이 판 해 보기", "녹화_메모": f"1단계에서 {t['이름']} 예고가 뜬 판"})
    d = run_dir(run)
    with open(os.path.join(d, "raw.jsonl"), "w", encoding="utf-8") as f:
        for c in out: f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(len(out), "개 →", os.path.join(d, "raw.jsonl"))

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["build", "api", "ingest", "template"])
    ap.add_argument("--run", required=True); ap.add_argument("--per-type", type=int, default=2)
    ap.add_argument("--model", default="claude-sonnet-5-5"); ap.add_argument("--game", default=DEFAULT_GAME)
    a = ap.parse_args()
    {"build": lambda: build(a.run, a.per_type, a.game), "api": lambda: api(a.run, a.model),
     "ingest": lambda: ingest(a.run), "template": lambda: template(a.run, a.game)}[a.cmd]()
