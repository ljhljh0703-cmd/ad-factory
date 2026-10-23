"""작은 표본용 통계: 비율의 윌슨 구간, 두 비율 비교에 필요한 표본, 두 비율 차이 검정, 홈 보정.

외부 패키지 없이 표준 라이브러리만 쓴다(맥 앱·클라우드·CI 어디서나 같은 값).
"""
import math
from statistics import NormalDist

_N = NormalDist()


def z(p):
    """누적확률 p에 해당하는 표준정규 값."""
    return _N.inv_cdf(p)


def wilson(k, n, conf=0.95):
    """k/n 비율의 윌슨 신뢰구간 (아래, 위). n이 0이면 (None, None)."""
    if not n:
        return (None, None)
    zz = z(1 - (1 - conf) / 2)
    p = k / n
    den = 1 + zz * zz / n
    mid = (p + zz * zz / (2 * n)) / den
    half = zz * math.sqrt(p * (1 - p) / n + zz * zz / (4 * n * n)) / den
    return (max(0.0, mid - half), min(1.0, mid + half))


def upper_zero(n, conf=0.95):
    """0건을 봤을 때 진짜 비율의 위쪽 한계(정확한 이항 계산). 3의 규칙(95%에서 약 3/n)과 같은 꼴."""
    if not n:
        return None
    return 1 - (1 - conf) ** (1 / n)


def n_per_arm(p0, mde, alpha=0.05, power=0.8, k=1):
    """기준 비율 p0에서 절대 차이 mde를 찾으려면 한 쪽에 필요한 표본 수(양측 검정).

    k: 같은 때 비교하는 쌍의 수. 본페로니로 alpha/k를 써서 보수적으로 잡는다.
    """
    p1 = min(max(p0 + mde, 1e-9), 1 - 1e-9)
    a = alpha / max(1, k)
    za, zb = z(1 - a / 2), z(power)
    pbar = (p0 + p1) / 2
    num = (za * math.sqrt(2 * pbar * (1 - pbar)) + zb * math.sqrt(p0 * (1 - p0) + p1 * (1 - p1))) ** 2
    return math.ceil(num / (mde * mde))


def two_prop_p(k1, n1, k2, n2):
    """두 비율이 같다는 가정에서 양측 p값(합동 z 검정). 표본이 없으면 None."""
    if not n1 or not n2:
        return None
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se == 0:
        return 1.0
    zz = (k1 / n1 - k2 / n2) / se
    return 2 * (1 - _N.cdf(abs(zz)))


def holm(pvals, alpha=0.05):
    """여러 비교의 p값 목록 → 같은 순서로 「차이 있음」 참거짓(홈 단계 보정)."""
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    out = [False] * len(pvals)
    for rank, i in enumerate(order):
        if pvals[i] <= alpha / (len(pvals) - rank):
            out[i] = True
        else:
            break
    return out


def r(x, nd=3):
    return None if x is None else round(x, nd)
