"""M3 표준계약서 비교의 입력·출력 모델 (초안)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# 찾지 못했다는 것이 표준과 같다는 뜻이 아님을 모든 결과에 붙인다 (명세서 8절)
DISCLAIMER = "찾지 못했다는 것이 표준과 같다는 뜻은 아닙니다."

Status = Literal["different", "needs_check", "none_detected", "not_found"]

STATUS_MEANING = {
    "different": "표준계약서와 다른 지점을 찾음 (두 원문 인용이 확인됨)",
    "needs_check": "확인 필요: 근거 인용을 확인하지 못했거나 답이 불완전함",
    "none_detected": "다른 지점을 찾지 못함 (표준과 같다는 뜻이 아님)",
    "not_found": "계약서에서 대응하는 조항을 찾지 못함 (표준과 같다는 뜻이 아님)",
}


class StandardClause(BaseModel):
    """표준계약서의 조항 하나."""

    id: str = Field(description="표준 조항 id. 예: 's-07'")
    no: str | None = Field(default=None, description="표준계약서의 조항 번호 표기")
    title: str | None = None
    text: str = Field(description="표준계약서 원문")
    core: bool = Field(
        default=False,
        description="MVP에서 비교하는 정산 관련 조항 (오픈북 팀이 고름. 해설집의 '핵심' 표시가 아님)",
    )


class ComparisonItem(BaseModel):
    """표준 조항 하나에 대한 비교 결과."""

    standard_id: str
    standard_no: str | None = None
    standard_title: str | None = None
    core: bool = False
    user_clause_id: str | None = Field(default=None, description="대응하는 사용자 계약서 조항 id")
    status: Status
    difference: str | None = Field(
        default=None, description="다른 지점의 중립적 설명. 판단 표현 없음 (코드가 필터링)"
    )
    user_quote: str | None = None
    standard_quote: str | None = None
    notice: str | None = Field(default=None, description="status가 different가 아니면 붙는 안내")


class ComparisonResult(BaseModel):
    contract_id: str
    items: list[ComparisonItem]
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER
