import os, json

ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.environ.get("ADF_ROOT") or os.path.dirname(ENGINE)


def p(*a):
    return os.path.join(ROOT, *a)


def rel(path):
    try:
        r = os.path.relpath(os.path.abspath(path), ROOT)
        return path if r.startswith("..") else r
    except ValueError:
        return path


def prices():
    """모델별 100만 토큰당 달러. 확인한 값만 적는다. 없으면 비용은 토큰 수로만 남는다."""
    f = os.path.join(ENGINE, "prices.json")
    return json.load(open(f, encoding="utf-8")) if os.path.exists(f) else {}
