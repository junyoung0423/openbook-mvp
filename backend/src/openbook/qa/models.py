"""M7 조항 Q&A 출력 모델."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

# 모든 답에 붙인다 (명세서 8절: 근거 조항, 기준일, 전문가 상담 안내)
QA_NOTICE = (
    "계약서 원문을 찾아 옮겨 보여 드린 것이며 법률 자문이 아닙니다. "
    "중요한 결정 전에는 변호사 등 전문가와 상담하세요."
)
NOT_FOUND_ANSWER = "계약서에서 이 질문에 대한 근거 조항을 찾지 못했습니다."
TEMPLATE_ANSWER = "관련 조항을 찾았습니다. 아래 원문을 직접 확인하세요."
CALC_ANSWER = (
    "관련 조항을 찾았습니다. 금액 계산은 정산 대조 화면에서 확인하세요. "
    "아래 원문을 직접 확인하세요."
)

Source = Literal["contract", "standard", "law"]


class Citation(BaseModel):
    """답의 근거. quote는 원문에 글자 그대로 있는 것이 코드로 확인된 문장만 남는다."""

    source: Source = Field(description="contract=사용자 계약서, standard=표준계약서, law=법령")
    clause_id: str
    clause_no: str | None = None
    clause_title: str | None = None
    quote: str
    law_name: str | None = Field(default=None, description="source=law일 때 법령명")
    effective_date: date | None = Field(default=None, description="source=law일 때 원문 시행일")
    source_url: str | None = None


class QAResult(BaseModel):
    """POST /contracts/{id}/qa 응답 본문 (초안)."""

    contract_id: str
    question: str
    found: bool = Field(description="근거 조항을 찾았는가. false면 answer는 '찾지 못함' 문장")
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    basis: str | None = Field(
        default=None, description="표준계약서를 인용했을 때 그 기준 (고시 번호·날짜)"
    )
    notice: str = QA_NOTICE
    warnings: list[str] = Field(default_factory=list)
