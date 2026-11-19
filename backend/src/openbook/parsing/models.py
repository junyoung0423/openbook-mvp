"""문서 파싱 모듈의 외부 인터페이스 모델."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Point(BaseModel):
    x: float
    y: float


class ParsedElement(BaseModel):
    id: int | str | None = None
    page: int | None = None
    category: str
    text: str
    coordinates: list[Point] = Field(default_factory=list)
    html: str | None = None


class ParsedDocument(BaseModel):
    """파서 종류와 무관하게 API 서버가 받는 결과."""

    text: str
    elements: list[ParsedElement] = Field(default_factory=list)
    tables: list[ParsedElement] = Field(default_factory=list)
