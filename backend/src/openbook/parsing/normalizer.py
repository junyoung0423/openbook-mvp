"""Upstage 결과를 조항 분할기에 안전한 줄바꿈 보존 평문으로 정규화한다."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

from openbook.parsing.errors import DocumentParseError
from openbook.parsing.models import ParsedDocument, ParsedElement, Point

_BLOCK_TAGS = {
    "p",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "tr",
    "table",
    "ul",
    "ol",
}


class _PlainTextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "br":
            self.parts.append("\n")
        elif tag in {"td", "th"} and self.parts and not self.parts[-1].endswith(("\n", "\t")):
            self.parts.append("\t")
        elif tag in _BLOCK_TAGS and self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _BLOCK_TAGS and (not self.parts or not self.parts[-1].endswith("\n")):
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return normalize_plain_text("".join(self.parts))


def html_to_plain_text(html: str) -> str:
    parser = _PlainTextHTMLParser()
    parser.feed(html)
    parser.close()
    return parser.text()


def markdown_to_plain_text(markdown: str) -> str:
    lines: list[str] = []
    for raw in normalize_plain_text(markdown).split("\n"):
        line = re.sub(r"^\s{0,3}#{1,6}\s+", "", raw)
        line = re.sub(r"^\s*[-*+]\s+", "", line)
        line = re.sub(r"^\s*\d+\.\s+", lambda m: m.group(0).lstrip(), line)
        line = line.replace("**", "").replace("__", "")
        lines.append(line)
    return normalize_plain_text("\n".join(lines))


def normalize_plain_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\ufeff", "")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _element_text(element: dict[str, Any]) -> str:
    content = element.get("content") or {}
    text = content.get("text") or ""
    if text.strip():
        return normalize_plain_text(text)
    html = content.get("html") or ""
    if html.strip():
        return html_to_plain_text(html)
    markdown = content.get("markdown") or ""
    if markdown.strip():
        return markdown_to_plain_text(markdown)
    return ""


def normalize_upstage_response(payload: dict[str, Any]) -> ParsedDocument:
    raw_elements = payload.get("elements")
    if raw_elements is not None and not isinstance(raw_elements, list):
        raise DocumentParseError("Document Parse 응답 형식이 예상과 다릅니다.")

    elements: list[ParsedElement] = []
    tables: list[ParsedElement] = []
    for raw in raw_elements or []:
        if not isinstance(raw, dict):
            continue
        text = _element_text(raw)
        content = raw.get("content") or {}
        html = content.get("html") if isinstance(content, dict) else None
        coords = raw.get("coordinates") or []
        points = [Point.model_validate(point) for point in coords if isinstance(point, dict)]
        element = ParsedElement(
            id=raw.get("id"),
            page=raw.get("page"),
            category=str(raw.get("category") or "unknown"),
            text=text,
            coordinates=points,
            html=html,
        )
        elements.append(element)
        if element.category == "table":
            tables.append(element)

    # 요소별로 한 줄 경계를 보존하면 `제N조`, `N.` 제목 앞에 HTML/Markdown 표식이 붙지 않는다.
    element_text = "\n".join(e.text for e in elements if e.text)
    text = normalize_plain_text(element_text)

    if not text:
        content = payload.get("content") or {}
        if isinstance(content, dict):
            text = normalize_plain_text(content.get("text") or "")
            if not text and content.get("html"):
                text = html_to_plain_text(content["html"])
            if not text and content.get("markdown"):
                text = markdown_to_plain_text(content["markdown"])

    if not text:
        raise DocumentParseError("Document Parse 결과에 읽을 수 있는 텍스트가 없습니다.")

    return ParsedDocument(text=text, elements=elements, tables=tables)
