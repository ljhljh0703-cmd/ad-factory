# 광고 공장 저장소: 클라우드 세션 안내

이 저장소는 맥의 광고 공장 앱과 Code 탭 클라우드 세션이 같이 쓴다. 맥 앱은 AI 단계에서 요청문만 남기고 멈춘다(`runs/jobs/B*/request-*.md`). 클라우드 세션은 그 요청에 답만 넣는다.

## 「대기 중인 거 처리해」(또는 「응답해」)를 받으면

```
cd engine && python3 -m adf answer
```

- 저장소를 받고, 기다리는 요청마다 `claude -p` 로 답을 만들어 `response-*.txt` 와 `response-*.meta.json`(토큰 수)을 넣고, 커밋·푸시까지 한다.
- 끝나면 처리한 건수, 작업 번호, 걸린 초만 짧게 알린다. 작가는 맥 앱에서 「클라우드 결과 받기」를 누른다.
- 요청문 내용을 고치거나, 답을 직접 쓰거나, 다른 파일(사실표·기준표·작업 상태)을 고치지 않는다. 판정은 요청문이 시키는 그대로 `claude -p` 에 맡긴다.
- 커밋 전에 `git config user.name`·`user.email` 이 비어 있으면 저장소 소유자 이름(ljhljh0703-cmd)으로 저장소 안에서만 정한다.

## 그 밖의 요청

엔진 사용법은 `engine/README.md`, 녹화 장면은 `RECORDING.md`, 지금까지 한 일은 `PROCESS.md`·`EXTENSION.md`.
