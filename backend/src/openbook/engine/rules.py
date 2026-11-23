"""계산 규칙 R1–R12 (허정민 님 초안 R1–R10 2026-11-18, R11·R12 2026-11-23, 후차감·별도만).

정답 케이스: tests/calc_cases/C01–C20 (손계산 검산표, 금액은 모두 가상).
정산서 양식은 지급내역형: 매출액 → 회사입금액 → 정산액 → 원천징수 → 작가지급액 (비고에 MG공제).

기본 모델 (기간 t마다, 후차감)
    S_t = r × (G_t − D_t)            작가 몫 (원 미만까지 정확한 값)
    P_t = max(0, S_t − B_{t−1})      지급액(세전), 원 미만 버림
    B_t = max(0, B_{t−1} − S_t)      남은 MG (원 미만까지 정확한 값)   (B_0 = MG 금액)

| #   | 규칙 |
|-----|------|
| R1  | 공제 D = Σ(비율 × G) + Σ정액. 총매출 기준 계약에만 쓴다. |
| R2  | 매출 기준이 총매출이면 G = 정산서 '매출액', 순매출이면 G = '회사입금액'이고 공제 목록은 쓰지 않는다 (이중 차감 방지). |
| R3  | 원 미만은 지급액 P에서 한 번만 버린다. 공제·작가 몫·남은 MG는 원 미만까지 그대로 이어 간다. |
| R4  | 별도(MG를 RS에서 회수하지 않음): P = S. |
| R5  | 매출 0원이면 S = 0. 작가 몫이 음수면 P = 0이고, 후차감은 남은 MG에 더해 다음 달 작가 몫에서 먼저 뺀다. |
| R6  | S = B면 P = 0, B = 0 (식 그대로). |
| R7  | 정산서 '작가지급액'을 계산한 실지급액(P − 원천징수)과 비교한다. |
| R8  | 미회수 MG 처리 방식(mg_carryover)은 계산에 쓰지 않는다 (표시만). |
| R9  | 같은 계약서의 정산서를 기간 순으로 이어 계산한다. 첫 정산서의 B_0는 MG 금액. |
| R10 | 계산 불가면 그 계약의 금액을 하나도 표시하지 않는다: 필수 항목 비어 있음, MG 차감 방식 알 수 없음(선차감 포함), 구간별 RS, 매출 기준 기타, 후차감 계약의 빠진 달, 별도 계약의 음수 매출. |
| R11 | 원천징수: 소득세 = P × 3%(10원 미만 버림), 지방소득세 = 소득세 × 10%(10원 미만 버림). P가 0원이면 0원. |
| R12 | 정산서 '정산액'을 작가 몫 S(원 미만 버림)와 비교한다. 회수 중이라 작가지급액이 0원인 달의 배분율 오류도 여기서 잡는다. |

차이는 모두 '정산서 값 − 계산 값'이다 (음수면 정산서가 적다). 허용 오차 없음.

정할 것 (허정민 님 확인)
- 원천징수율: 2.2% 인하안이 통과되면 2027-01-01 이후 지급분부터 바뀐다 → WITHHOLDING_RATES에 날짜별로 둔다.
  지급일을 입력받지 않으므로 정산 기간 끝날을 기준으로 고른다.
- 소액부징수(소득세 1,000원 미만이면 떼지 않음)는 규칙에 없어 넣지 않았다.
- 별도 계약의 빠진 달은 계산에 영향이 없어 계산 불가로 두지 않고 질문만 한다 (R10-5는 후차감 기준으로 해석).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

RULES_VERSION = "draft-2026-11-23-r12"

# (이 날짜부터, 소득세율). 지방소득세는 소득세의 10%.
WITHHOLDING_RATES: tuple[tuple[date, Decimal], ...] = ((date(1900, 1, 1), Decimal("0.03")),)
LOCAL_TAX_RATE = Decimal("0.1")

# R10 계산 불가 문구 (검산표와 같은 글자)
UNSUPPORTED = "계산 불가: {what}이(가) {why}"
EMPTY = "비어 있음"
UNKNOWN = "알 수 없음"
TIERED = "구간별이라 계산하지 않음"
NO_STATEMENT = "정산서 없음"
NEGATIVE_SEPARATE = "매출 음수(별도 계약)"
NO_NET_REVENUE = "회사입금액 없음(순매출 기준)"
OVERLAP = "기간이 겹치는 정산서 있음"

LABELS = {
    "mg_amount": "MG 금액",
    "mg_recoup": "MG 차감 방식",
    "rs_rate": "RS율",
    "revenue_base": "매출 기준",
    "deductions": "공제 항목",
}


def unsupported(what: str, why: str) -> str:
    return UNSUPPORTED.format(what=what, why=why)


def income_tax_rate(on: date) -> Decimal:
    rate = WITHHOLDING_RATES[0][1]
    for since, r in WITHHOLDING_RATES:
        if on >= since:
            rate = r
    return rate
