"""조항 분할 결과 스키마 (M2 출력, 명세서 4절·5절 clauses 테이블).

초안(v1): 팀 리뷰 후 확정한다.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class Clause(BaseModel):
    """계약서 조항 하나."""

    id: str = Field(
        description="조항 고유 id. 예: 'c-07'. 조건(terms)의 source_clause_id가 가리킨다."
    )
    no: str | None = Field(
        default=None,
        description="계약서에 적힌 조항 번호 표기 그대로. 예: '제7조'. 번호가 없으면 null.",
    )
    title: str | None = Field(default=None, description="조항 제목. 없으면 null.")
    text: str = Field(
        description=(
            "조항 본문 원문. 제목 줄(예: '제4조 (선급금)')은 no·title에 있으므로 빼고, "
            "그 아래 본문을 요약·수정 없이 그대로."
        )
    )
    type_id: str | None = Field(
        default=None,
        description="조항유형 id (clause_types.yaml 기준). 분류하지 못했으면 null.",
    )
    std_clause_id: str | None = Field(
        default=None,
        description="매칭된 표준계약서 조항 id. 매칭이 없으면 null (표준과 같다는 뜻이 아님).",
    )


class ClauseSplitResult(BaseModel):
    """GET /contracts/{id}/clauses 응답 본문."""

    contract_id: str
    clauses: list[Clause]

    @model_validator(mode="after")
    def _unique_ids(self) -> ClauseSplitResult:
        ids = [c.id for c in self.clauses]
        if len(ids) != len(set(ids)):
            raise ValueError("조항 id가 중복되었습니다.")
        return self
