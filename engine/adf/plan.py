"""대화형 기획: 기획자·마케터가 말로 쓴 요청을 캠페인 명세(JSON)로 바꾸고, 규칙으로 검사한 뒤 작업으로 넣는다.

1) AI가 요청을 명세로 옮긴다(모르는 값은 비우고 「물어볼_것」에 적는다. 지어내지 않는다)
2) 규칙 검사: 게임 어댑터가 있는지, 광고 게시가 허락된 게임인지, 유형·채널이 기준표에 있는지,
   숫자·순위·보상 약속 같은 금지 문구를 요청했는지, 유료 집행인지(유료는 사람 승인 필요)
3) 빠진 값이 있으면 질문만 돌려준다. 다 차면 대본 생성 → 생성분 심사 묶음을 넣는다
"""
import json, os, re, glob

from . import paths, pipelines

TYPES = ["질 뻔하다 뒤집기", "열린 끝", "선택 순간", "손 화면·반응", "같은 판 도전", "세계관 도입 → 실제 플레이", "답답한 플레이"]
CHANNELS = {"tiktok": "틱톡", "reels": "인스타그램 릴스", "shorts": "유튜브 쇼츠"}
BANNED_ASK = [(r"1위|순위|평점|최고의", "근거 없는 순위·평점(R2)"), (r"상품권|경품|현금|보상 지급|추첨", "경품·보상 약속(R4)"),
              (r"연예인|유명인|인플루언서 얼굴", "실제 인물 합성·사칭(R3)"), (r"가짜 후기|사용자 후기인 척|리뷰 지어", "지어낸 후기(R3)"),
              (r"게임에 없는|다른 게임 화면|핀 뽑기", "게임에 없는 장면(R1)")]

SCHEMA = {
    "게임": "어댑터 id(예: jelly-panic, gem-tower). 모르면 빈 값",
    "목표": "설치·첫 판·재방문 중 무엇을 늘리고 싶은지, 요청에 있는 말 그대로",
    "채널": ["tiktok|reels|shorts"],
    "유형": {"유형 이름": "개수"},
    "총_개수": "정수",
    "유료_집행": "true|false|null(말이 없으면 null)",
    "예산": "말한 금액 그대로, 없으면 null",
    "기간": "말한 기간 그대로, 없으면 null",
    "꼭_넣을_것": ["요청에 있는 것만"],
    "빼야_할_것": ["요청에 있는 것만"],
    "요청_원문_중_금지_의심": ["순위·보상·실존 인물·게임에 없는 장면 등을 요청한 부분을 원문 그대로"],
    "물어볼_것": ["정하지 못한 값마다 질문 한 줄"],
}


def games():
    out = {}
    for f in glob.glob(paths.p("adapters", "*", "adapter.json")):
        m = json.load(open(f, encoding="utf-8")); out[m["id"]] = m
    return out


def prompt(text):
    gs = {k: {"이름": v["이름"], "광고_게시": v.get("광고_게시")} for k, v in games().items()}
    return f"""너는 게임 광고 캠페인 기획을 받아 적는 사람이다. 아래 요청을 명세 JSON 하나로 옮긴다.
요청에 없는 값은 지어내지 말고 비우고, 「물어볼_것」에 질문으로 적는다.

## 쓸 수 있는 게임
{json.dumps(gs, ensure_ascii=False)}

## 광고 유형(이 이름만 쓴다)
{json.dumps(TYPES, ensure_ascii=False)}

## 채널
{json.dumps(CHANNELS, ensure_ascii=False)}

## 명세 형식
{json.dumps(SCHEMA, ensure_ascii=False, indent=1)}

## 요청
{text}

## 출력
JSON 하나만. 설명 없이."""


def parse(text):
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else {}


def check(spec, request_text):
    gs = games(); issues, asks, needs_approval = [], [], []
    soft = list(spec.get("물어볼_것") or [])  # AI가 덧붙인 확인 질문: 보여 주되 진행을 막지 않는다
    g = spec.get("게임")
    if not g: asks.append("어느 게임 광고인가요?")
    elif g not in gs: issues.append(f"어댑터가 없는 게임: {g}. 먼저 게임 어댑터를 붙여야 합니다")
    else:
        pub = gs[g].get("광고_게시", {})
        if g != "jelly-panic": issues.append(f"대본 생성기가 아직 {gs[g]['이름']} 사실표를 읽지 못합니다(생성기 게임 분리는 다음 일)")
        if not pub.get("가능", True): issues.append(f"{gs[g]['이름']}: 게시 불가로 표시된 게임({pub.get('메모')}). 내부 시험용 대본만 만들고 게시 단계는 막습니다")
    bad_types = [t for t in (spec.get("유형") or {}) if t not in TYPES]
    if bad_types: issues.append(f"기준표에 없는 유형: {bad_types}")
    bad_ch = [c for c in (spec.get("채널") or []) if c not in CHANNELS]
    if bad_ch: issues.append(f"모르는 채널: {bad_ch}")
    if not spec.get("채널"): asks.append("어느 채널에 올리나요? (틱톡·릴스·쇼츠)")
    if not spec.get("유형") and not spec.get("총_개수"): asks.append("몇 개를, 어떤 유형으로 만들까요?")
    for rx, why in BANNED_ASK:
        if re.search(rx, request_text): issues.append(f"요청에 금지 의심: {why}. 이 부분은 대본에 넣지 않습니다")
    if spec.get("유료_집행"): needs_approval.append("유료 집행: 금액·계정 연결은 사람이 승인해야 시작합니다")
    if spec.get("유료_집행") is None: asks.append("무료 게시만 하나요, 유료 집행도 하나요?")
    return {"문제": issues, "물어볼_것": list(dict.fromkeys(asks)), "확인하면_좋은_것": soft, "승인_필요": needs_approval,
            "진행": not asks and not any(k in i for i in issues for k in ("어댑터가 없는", "기준표에 없는", "모르는 채널", "생성기가 아직", "게시 불가"))}


def enqueue(spec, run):
    total = int(spec.get("총_개수") or sum(int(v) for v in (spec.get("유형") or {}).values()) or 6)
    per = max(1, round(total / max(1, len(spec.get("유형") or TYPES[:6]))))
    a = pipelines.enqueue("대본", {"run": run, "per_type": per}, note=f"기획에서 {spec.get('목표', '')}")
    b = pipelines.PIPELINES["생성분심사"]
    js = pipelines.enqueue("생성분심사", {"game": spec["게임"], "run": "J" + run, "set": run}, note="기획에서")
    js[0].d["앞_작업"] = [a[-1].id]; js[0].save()
    return [j.id for j in a + js]
