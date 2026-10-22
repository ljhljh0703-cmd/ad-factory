"""사실표 자동 대조: 공개판 소스에서 플레이어가 보는 글자와 규칙 숫자를 뽑아 사실표와 맞춰 본다.

어긋남이 하나라도 있으면 심사 단계를 막는다(사실표가 틀리면 심사기가 틀린 사실로 판정하기 때문).
뽑는 법은 어댑터마다 adapter.json 의 「자동_대조」에 적는다.

  안내_함수 : 이 함수에 넘기는 글자 = 게임 안 안내(토스트). 첫 인자가 열쇠인 함수는 「한 번만」으로 본다
  안내_표   : 안내 글자를 모아 둔 표 이름(객체·배열에 넣은 글자)
  끝_변수   : 판이 끝날 때 보여 주는 글자를 넣는 변수 이름
  화면_요소 : 화면 요소 id → 사실표에 있어야 할 말. CSS 로 조건부 숨김이 있으면 함께 알린다
  상수      : 코드 정규식에서 뽑은 숫자 → 사실표 어느 칸에 그 숫자가 있어야 하는지
  비교_목록 : 사실표에서 안내 전체 목록으로 쓰는 칸(빌드의 안내와 양쪽으로 맞춰 봄)
"""
import json, os, re, glob

HANGUL = re.compile(r"[가-힣]")
STR = r"""'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)\""""


def norm(s):
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _expr_to_pattern(expr):
    """'임무: ' + stageGoalDesc(x) → ('임무: {}', 정규식). 글자 조각만 남기고 나머지는 빈칸으로."""
    parts, last = [], 0
    for m in re.finditer(STR, expr):
        between = expr[last:m.start()]
        if parts and re.search(r"[^\s+]", between): parts.append(None)
        elif not parts and re.search(r"[^\s+(]", between.strip()): parts.append(None)
        parts.append(m.group(1) if m.group(1) is not None else m.group(2)); last = m.end()
    if re.search(r"[^\s+);]", expr[last:]): parts.append(None)
    text = "".join("{}" if p is None else p for p in parts)
    rx = "".join(".*?" if p is None else re.escape(norm(p)) for p in parts)
    return norm(text), re.compile("^" + rx + "$")


def branches(expr):
    """삼항식 cond ? A : B 를 A, B 로 나눈다(따옴표·괄호 안은 건드리지 않음)."""
    depth, q, qpos, nest, esc = 0, None, None, 0, False
    for i, ch in enumerate(expr):
        if q:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == q: q = None
            continue
        if ch in "'\"`": q = ch
        elif ch in "([{": depth += 1
        elif ch in ")]}": depth -= 1
        elif depth == 0 and ch == "?" and expr[i + 1:i + 2] not in ("?", ".") and expr[i - 1:i] != "?":
            if qpos is None: qpos = i
            else: nest += 1
        elif depth == 0 and ch == ":" and qpos is not None:
            if nest: nest -= 1
            else: return branches(expr[qpos + 1:i]) + branches(expr[i + 1:])
    return [expr]


def _call_args(src, fn):
    """fn( 첫 인자, 둘째 인자 ) 의 마지막 인자 식을 돌려준다(괄호 짝 맞춤)."""
    out = []
    for m in re.finditer(r"\b" + re.escape(fn) + r"\s*\(", src):
        i, depth, start = m.end(), 1, m.end()
        args, cur = [], start
        q = None
        while i < len(src) and depth:
            ch = src[i]
            if q:
                if ch == "\\": i += 1
                elif ch == q: q = None
            elif ch in "'\"`": q = ch
            elif ch in "([{": depth += 1
            elif ch in ")]}":
                depth -= 1
                if depth == 0: args.append(src[cur:i]); break
            elif ch == "," and depth == 1: args.append(src[cur:i]); cur = i + 1
            i += 1
        line = src.count("\n", 0, m.start()) + 1
        out.append((args, line))
    return out


def source_dir(adapter_dir, man=None):
    """소스 위치: 저장소를 받아 둔 곳이 있으면 거기, 없으면 어댑터의 공개판 사본(source-cache)."""
    man = man or json.load(open(os.path.join(adapter_dir, "adapter.json"), encoding="utf-8"))
    repo = os.environ.get("ADF_SRC_" + man["id"].replace("-", "_").upper()) or man["사실표"]["출처"].get("저장소_경로")
    return repo if repo and os.path.isdir(repo) else os.path.join(adapter_dir, "source-cache")


def refresh_cache(adapter_dir):
    """공개판 주소에서 사본 파일을 새로 받는다(파일 목록은 지금 사본과 같음). 받지 못하면 예전 사본을 그대로 쓴다."""
    import urllib.request
    man = json.load(open(os.path.join(adapter_dir, "adapter.json"), encoding="utf-8"))
    cache = os.path.join(adapter_dir, "source-cache"); base = man["빌드"].get("소스_주소") or man["빌드"]["주소"]
    got, failed = [], []
    for f in sorted(glob.glob(os.path.join(cache, "**", "*"), recursive=True)):
        if not os.path.isfile(f): continue
        rel = os.path.relpath(f, cache)
        url = base.rstrip("/") + "/" + (rel[len(man["빌드"].get("사본_앞부분", "")):] if rel.startswith(man["빌드"].get("사본_앞부분", "")) else rel)
        try:
            body = urllib.request.urlopen(url, timeout=20).read()
            open(f, "wb").write(body); got.append(rel)
        except Exception as e:
            failed.append(f"{rel}: {type(e).__name__}")
    return {"받음": len(got), "실패": failed}


def extract(adapter_dir):
    man = json.load(open(os.path.join(adapter_dir, "adapter.json"), encoding="utf-8"))
    cfg = man["자동_대조"]; base = source_dir(adapter_dir, man)
    files = [f for pat in cfg["소스"] for f in sorted(glob.glob(os.path.join(base, pat)))]
    src = {os.path.relpath(f, base): open(f, encoding="utf-8").read() for f in files}
    toasts, ends, consts, screen = [], [], [], []
    for fname, s in src.items():
        tables = {}
        for t in cfg.get("안내_표", []):
            body = re.search(re.escape(t) + r"\s*=\s*\{(.*?)\};", s, re.S)
            vals = [m.group(1) or m.group(2) for m in re.finditer(STR, body.group(1))] if body else []
            vals += [m.group(1) or m.group(2) for m in re.finditer(re.escape(t) + r"\[[^\]]+\]\s*=\s*(?:" + STR + ")", s)]
            tables[t] = [v for v in vals if HANGUL.search(v)]
        for fn in cfg.get("안내_함수", []):
            once = fn in cfg.get("한번만_함수", [])
            for args, line in _call_args(s, fn):
                if not args: continue
                expr = args[-1].strip()
                if re.match(r"^(msg|text|s)$", expr): continue  # 함수 정의 안쪽
                tab = next((t for t in tables if expr.startswith(t + "[")), None)
                if tab:
                    for v in tables[tab]:
                        toasts.append({"글자": norm(v), "줄": f"{fname}:{line}", "한번만": once, "출처": tab})
                    continue
                for br in branches(expr):
                    br = br.strip().rstrip(")").strip() if br.count(")") > br.count("(") else br.strip()
                    if not HANGUL.search(br): continue
                    if re.match(r"^\(?\s*[A-Z_]+\[", br) and "??" in br:  # 표 조회 ?? 기본 글자
                        br = br.split("??", 1)[1]
                    text, rx = _expr_to_pattern(br)
                    if text.replace("{}", "").strip() == "": continue
                    if cfg.get("안내_제외") and re.search(cfg["안내_제외"], text): continue
                    toasts.append({"글자": text, "패턴": rx.pattern, "줄": f"{fname}:{line}", "한번만": once})
        for var in cfg.get("끝_변수", []):
            for m in re.finditer(r"\b" + re.escape(var) + r"\s*=\s*([^;\n]+)", s):
                expr = m.group(1)
                for branch in re.split(r"\s[?:]\s", expr):
                    if HANGUL.search(branch):
                        text, rx = _expr_to_pattern(branch)
                        ends.append({"글자": text, "패턴": rx.pattern, "줄": f"{fname}:{s.count(chr(10), 0, m.start()) + 1}"})
        for el in cfg.get("끝_요소", []):
            for m in re.finditer(r"(?:\$\(|getElementById\()\s*['\"]" + re.escape(el) + r"['\"]\s*\)\.textContent\s*=\s*([^;\n]+)", s):
                for br in branches(m.group(1)):
                    br = br.replace("`", "'").replace("${", "' + (").replace("}", ") + '")
                    if HANGUL.search(br):
                        text, rx = _expr_to_pattern(br)
                        ends.append({"글자": text, "패턴": rx.pattern, "줄": f"{fname}:{s.count(chr(10), 0, m.start()) + 1}"})
        for c in cfg.get("상수", []):
            for m in re.finditer(c["코드"], s):
                consts.append({**c, "값": m.group(1), "줄": f"{fname}:{s.count(chr(10), 0, m.start()) + 1}"})
        for e in cfg.get("화면_요소", []):
            if re.search(r"id=[\"']" + re.escape(e["id"]) + r"[\"']", s) or re.search(r"getElementById\(['\"]" + re.escape(e["id"]), s):
                hidden = []
                for mm in re.finditer(r"@media([^{]+)\{((?:[^{}]*\{[^{}]*\})*)\s*\}", s):
                    if re.search(r"#" + re.escape(e["id"]) + r"\s*\{[^}]*display\s*:\s*none", mm.group(2)):
                        hidden.append(norm(mm.group(1)))
                screen.append({**e, "있음": True, "숨는_조건": hidden, "파일": fname})
    # 중복 정리
    def uniq(rows, key="글자"):
        seen, out = set(), []
        for r in rows:
            if r[key] in seen: continue
            seen.add(r[key]); out.append(r)
        return out
    return {"어댑터": man["id"], "파일": list(src), "안내": uniq(toasts), "끝": uniq(ends), "상수": consts, "화면": uniq(screen, "id")}


def _get(d, path):
    for k in path.split("."):
        d = d[int(k)] if isinstance(d, list) else d.get(k, {})
    return d


def compare(adapter_dir, facts_path):
    man = json.load(open(os.path.join(adapter_dir, "adapter.json"), encoding="utf-8"))
    cfg = man["자동_대조"]
    facts = json.load(open(facts_path, encoding="utf-8"))
    blob = norm(json.dumps(facts, ensure_ascii=False))
    ex = extract(adapter_dir)
    issues = []

    def in_facts(item):
        t = item["글자"].replace("{}", "")
        rx = re.compile(item["패턴"]) if item.get("패턴") else None
        if "{}" not in item["글자"] and item["글자"] in blob: return True
        # 사실표 쪽 문장에 빈칸 부분(숫자 등)이 채워져 들어간 경우
        for frag in re.findall(r"\"((?:[^\"\\]|\\.)*)\"", json.dumps(facts, ensure_ascii=False)):
            f = norm(re.sub(r"\s*\([^)]*\)\s*$", "", frag))
            if rx and (rx.match(f) or rx.match(norm(frag))): return True
            if "{}" in item["글자"]:
                pieces = [p for p in item["글자"].split("{}") if p.strip()]
                if pieces and all(p.strip() in frag for p in pieces): return True
        return False

    for t in ex["안내"]:
        if not in_facts(t):
            issues.append({"종류": "빌드에 있는 안내가 사실표에 없음", "글자": t["글자"], "위치": t["줄"]})
    once = [t for t in ex["안내"] if t.get("한번만")]
    if once and cfg.get("한번만_사실표_말") and cfg["한번만_사실표_말"] not in blob:
        issues.append({"종류": "안내가 판마다 한 번만 뜨는데 사실표에 없음", "안내_수": len(once), "있어야_할_말": cfg["한번만_사실표_말"]})
    listed = _get(facts, cfg["비교_목록"]) if cfg.get("비교_목록") else []
    for f in listed:
        cands = {norm(f), norm(re.sub(r"\s*\([^)]*\)\s*$", "", f))}
        if not any(c == t["글자"] or (t.get("패턴") and re.match(t["패턴"], c)) for c in cands for t in ex["안내"]):
            issues.append({"종류": "사실표 안내가 빌드에 없음", "글자": f})
    for e in ex["끝"]:
        if not in_facts(e):
            issues.append({"종류": "빌드의 판 끝 문구가 사실표에 없음", "글자": e["글자"], "위치": e["줄"]})
    for c in ex["상수"]:
        val = _get(facts, c["사실"])
        want = c["포함"].replace("{값}", c["값"])
        if want not in json.dumps(val, ensure_ascii=False):
            issues.append({"종류": "규칙 숫자가 사실표와 다름", "코드값": c["값"], "사실표_칸": c["사실"], "있어야_할_말": want, "위치": c["줄"]})
    for e in cfg.get("화면_요소", []):
        hit = next((s for s in ex["화면"] if s["id"] == e["id"]), None)
        want = e["사실표_말"]
        area = norm(json.dumps(_get(facts, e["사실표_칸"]), ensure_ascii=False)) if e.get("사실표_칸") else blob
        if hit and want not in area:
            issues.append({"종류": "빌드 화면 요소가 사실표에 없음", "요소": "#" + e["id"], "있어야_할_말": want})
        if not hit and want in area and not e.get("없어도_됨"):
            issues.append({"종류": "사실표 화면 요소가 빌드에 없음", "요소": "#" + e["id"], "말": want})
        if hit and hit["숨는_조건"]:
            note = e.get("숨김_사실표_말")
            if not note or note not in area:
                issues.append({"종류": "화면 요소가 조건부로 숨음(사실표에 없음)", "요소": "#" + e["id"], "조건": hit["숨는_조건"]})
    for e in cfg.get("없어야_할_요소", []):
        if any(re.search(e["패턴"], s) for s in [open(os.path.join(source_dir(adapter_dir, man), f), encoding="utf-8").read() for f in ex["파일"]]):
            issues.append({"종류": "사실표 「없는 것」이 빌드에 있음", "말": e["사실표_말"], "패턴": e["패턴"]})
        elif e["사실표_말"] not in blob:
            issues.append({"종류": "빌드에 없는 화면을 사실표 「없는 것」에 적지 않음", "말": e["사실표_말"]})
    return {"어댑터": man["id"], "사실표": os.path.basename(facts_path), "사실표_판": facts.get("사실표_판"),
            "뽑은_것": {k: len(v) for k, v in ex.items() if isinstance(v, list)}, "어긋남": issues,
            "결론": "통과" if not issues else "막음"}, ex
