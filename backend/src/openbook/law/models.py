"""법령 조문 모델. 조문 하나가 검색·인용의 한 단위다."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class LawArticle(BaseModel):
    """법령 조문 하나 (항·호·목을 이어 붙인 원문)."""

    id: str = Field(description="프롬프트·인용에 쓰는 id. 예: 'l-저작권법-제9조'")
    law_name: str = Field(description="법령명. 예: '저작권법'")
    article_no: str = Field(description="조문 번호 표기. 예: '제9조', '제9조의2'")
    title: str | None = Field(default=None, description="조문 제목. 예: '업무상저작물의 저작자'")
    text: str = Field(description="조문 원문 (항·호·목 포함)")
    effective_date: date | None = Field(default=None, description="이 원문의 시행일")
    source_url: str | None = None
