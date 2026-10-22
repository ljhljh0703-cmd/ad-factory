"""묶음: 자주 쓰는 단계 순서. 앞 작업이 '완료'여야 다음 작업이 돈다."""
from . import jobs

PIPELINES = {
    "심사": {
        "설명": "평가셋이나 생성 회차 하나를 심사하고 채점한다",
        "단계": [("사실표.대조", ["game"]),
                 ("심사.요청문", ["run", "set"]),
                 ("심사.AI판정", ["run", "times", "model", "provider", "replay_from"]),
                 ("심사.합치기", ["run"]),
                 ("심사.채점", ["run", "block_on_expensive"])],
    },
    "생성분심사": {
        "설명": "생성 회차를 심사하고 「사람 확인」을 검토 대기열로 보낸다(정답이 없어 채점은 안 함)",
        "단계": [("사실표.대조", ["game"]),
                 ("심사.요청문", ["run", "set"]),
                 ("심사.AI판정", ["run", "times", "model", "provider", "replay_from"]),
                 ("심사.합치기", ["run"]),
                 ("검토.넣기", ["run"])],
    },
    "대본": {
        "설명": "사실표·기준표로 대본을 만들고 형식 검사까지",
        "단계": [("대본.요청문", ["run", "per_type"]),
                 ("대본.생성", ["run", "model", "provider", "replay"]),
                 ("대본.받기", ["run"])],
    },
    "주간성과": {
        "설명": "수집기에서 최근 7일 기록을 받아 광고별로 묶고 AI 주간 보고까지",
        "단계": [("성과.받기", ["out", "days"]),
                 ("성과.주간보고", ["events_dir", "platform_csv", "period", "note", "provider"])],
    },
    "대조": {
        "설명": "완성 영상과 대본을 화면 단위로 맞춰 본다",
        "단계": [("대조.시트", ["video", "out", "fps"]),
                 ("대조.판정", ["script", "out", "final", "model", "provider", "replay"])],
    },
}


def enqueue(name, args, note=""):
    spec = PIPELINES[name]
    made, prev = [], None
    for st, keys in spec["단계"]:
        a = {k: args[k] for k in keys if k in args}
        j = jobs.create(st, a, after=[prev.id] if prev else [], pipeline=name, note=note)
        made.append(j); prev = j
    return made
