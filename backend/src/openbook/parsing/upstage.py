"""Upstage Document Parse 어댑터."""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import Protocol

import httpx

from openbook.parsing.errors import (
    DocumentParseConfigError,
    DocumentParseError,
    DocumentParseTimeout,
    UnsupportedDocumentError,
)
from openbook.parsing.models import ParsedDocument, ParsedElement
from openbook.parsing.normalizer import normalize_plain_text, normalize_upstage_response

DEFAULT_URL = "https://api.upstage.ai/v1/document-digitization"
SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".hwp",
    ".hwpx",
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".tif",
    ".tiff",
    ".heic",
    ".webp",
}


class HTTPClient(Protocol):
    def post(self, url: str, **kwargs) -> httpx.Response: ...


class UpstageDocumentParser:
    def __init__(
        self,
        api_key: str,
        *,
        client: HTTPClient | None = None,
        timeout_seconds: float = 60.0,
        mode: str = "standard",
        base_url: str = DEFAULT_URL,
    ) -> None:
        if not api_key:
            raise DocumentParseConfigError("UPSTAGE_API_KEY가 설정되지 않았습니다.")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.mode = mode
        self.base_url = base_url
        self._client = client or httpx.Client(timeout=timeout_seconds)

    @classmethod
    def from_env(cls, **kwargs) -> "UpstageDocumentParser":
        return cls(os.getenv("UPSTAGE_API_KEY", ""), **kwargs)

    def parse_file(
        self,
        filename: str,
        content: bytes,
        *,
        mime_type: str | None = None,
    ) -> ParsedDocument:
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise UnsupportedDocumentError(f"지원하지 않는 파일 형식입니다: {suffix or '확장자 없음'}")
        if not content:
            raise DocumentParseError("빈 파일은 파싱할 수 없습니다.")

        mime = mime_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        try:
            response = self._client.post(
                self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"document": (filename, content, mime)},
                data={
                    "model": "document-parse",
                    "mode": self.mode,
                    "output_formats": '["text","html"]',
                    "coordinates": "true",
                },
                timeout=self.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise DocumentParseTimeout("Document Parse 요청 시간이 초과되었습니다.") from exc
        except httpx.HTTPError as exc:
            raise DocumentParseError(
                f"Document Parse 연결에 실패했습니다: {type(exc).__name__}"
            ) from exc

        if response.status_code != 200:
            # 응답 본문은 오류 메시지에 넣지 않는다. 외부 서비스가 원문을 되돌려 줄 가능성을 차단한다.
            raise DocumentParseError(f"Document Parse 호출에 실패했습니다: HTTP {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise DocumentParseError("Document Parse 응답 형식이 예상과 다릅니다.") from exc
        if not isinstance(payload, dict):
            raise DocumentParseError("Document Parse 응답 형식이 예상과 다릅니다.")
        return normalize_upstage_response(payload)


def parse_pasted_text(text: str) -> ParsedDocument:
    normalized = normalize_plain_text(text)
    if not normalized:
        raise DocumentParseError("빈 본문은 파싱할 수 없습니다.")
    elements = [
        ParsedElement(id=i, category="text", text=line)
        for i, line in enumerate(normalized.split("\n"))
        if line
    ]
    return ParsedDocument(text=normalized, elements=elements)
