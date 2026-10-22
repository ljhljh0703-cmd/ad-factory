---
created: 2026-10-22
updated: 2026-10-22
type: tool
state: provisional
related_to: ["[[applications/_portfolio/game-ad-factory/PLAN]]", "[[applications/_portfolio/game-ad-factory/CRITERIA]]", "[[applications/_portfolio/game-ad-factory/eval/README]]"]
---
<!-- 광고 소재 공장 1단계 3번: 소재 생성기. -->

# 광고 소재 생성기 (1단계 3번)

게임 사실표와 기준표를 읽어 AI에 줄 요청문을 만들고, AI가 낸 대본을 받아 형식을 검사한다.

## 흐름

1. `python3 generate.py build --run R01 --per-type 2`: 사실표(`game/jelly-panic.json`)와 기준표 1~3절을 묶어 `runs/R01/prompt.md` 를 만든다.
2. AI가 요청문대로 대본을 낸다. API 키가 있으면 `python3 generate.py api --run R01`, 없으면 Claude 세션이 요청문을 받아 `runs/R01/raw.jsonl` 로 저장한다.
3. `python3 generate.py ingest --run R01`: 받은 대본마다 번호와 출처 태그 붙은 링크를 달고 기계 검사(유형 이름, 게임 이름 위치, 자막, 끝 할 일, 숫자, 사실표의 「없는 것」, 세계관 도입부 그림 수·넘어가는 표시·그림 요청문 수)를 돌린다. 결과는 `candidates.jsonl` 과 `ingest-report.json`.
4. 내용 판정(게임에 있는 장면인지, 후기 흉내인지 등)은 다음 단계 심사기가 한다.

## 다른 게임

`--game gem-tower` 처럼 게임을 주면 `game/<게임>.json` 사실표를 읽는다. 게임 이름은 회차의 `run.json` 에 남고, 받기 단계와 심사기가 그 값을 따른다.

- 세계관 도입 유형은 사실표에 「광고_세계관」이 있는 게임만 만든다. 보석타워는 정한 세계관이 없어 5개 유형만 쓴다.
- 「광고에_쓰지_않는_것」이 있으면 요청문에 넣는다.
- 「광고_게시」가 막힘이면 후보마다 `게시: 막힘` 을 붙인다. 게시 승인 단계는 따로 게임 허락을 본다.
- 조합 기준선(template)은 젤리 패닉 위협 목록으로만 만든다.

## 비교용 틀 생성

`python3 generate.py template --run T01` 은 AI 없이 사실표 조합(위협 4종 × 후킹 3종)으로 12개를 만든다. AI 생성 결과와 같은 심사를 거쳐 통과율·다양성을 비교하는 기준선으로 쓴다.

## 그림

세계관 유형의 그림은 `그림_요청문` 을 작가 크롬의 웹 ChatGPT에 넣어 뽑는다. 다른 생성기는 쓰지 않는다. 뽑은 그림은 `runs/<회차>/images/` 에 둔다.

## 변경 기록

- 2026-10-22 첫 판. build · api · ingest · template.
- 2026-10-22 게임 분리(`--game`). 기준표 1-1의 「답답한 플레이」가 유형 목록에 빠져 있던 것을 넣음. 젤리 패닉 요청문은 이 유형 한 줄 말고는 예전과 같고, 예전 생성분 형식 검사 결과는 그대로.
