import httpx
import pytest

from openbook.clauses import split_clauses
from openbook.parsing import (
    DocumentParseError,
    DocumentParseTimeout,
    UnsupportedDocumentError,
    UpstageDocumentParser,
    parse_pasted_text,
)


def _payload():
    return {
        "api": "2.0",
        "elements": [
            {
                "id": 0,
                "page": 1,
                "category": "heading2",
                "content": {"text": "", "html": "<h2>제1조 (목적)</h2>", "markdown": ""},
                "coordinates": [{"x": 0.1, "y": 0.1}, {"x": 0.9, "y": 0.1}],
            },
            {
                "id": 1,
                "page": 1,
                "category": "paragraph",
                "content": {"text": "본 계약의 목적을 정한다.", "html": "", "markdown": ""},
                "coordinates": [],
            },
            {
                "id": 2,
                "page": 1,
                "category": "heading2",
                "content": {"text": "", "html": "<h2>제2조 (정산)</h2>", "markdown": ""},
                "coordinates": [],
            },
            {
                "id": 3,
                "page": 1,
                "category": "paragraph",
                "content": {"text": "정산은 매월 실시한다.", "html": "", "markdown": ""},
                "coordinates": [],
            },
            {
                "id": 4,
                "page": 1,
                "category": "table",
                "content": {
                    "text": "",
                    "html": "<table><tr><th>항목</th><th>금액</th></tr><tr><td>매출</td><td>1000</td></tr></table>",
                    "markdown": "",
                },
                "coordinates": [],
            },
        ],
    }


def test_upstage_html_is_plain_text_and_splitter_can_use_it():
    def handler(request: httpx.Request):
        return httpx.Response(200, request=request, json=_payload())

    client = httpx.Client(transport=httpx.MockTransport(handler))
    parser = UpstageDocumentParser("test-key", client=client)
    parsed = parser.parse_file("contract.docx", b"fake-docx")

    assert parsed.text.startswith("제1조 (목적)\n본 계약의 목적을 정한다.")
    assert "<h2>" not in parsed.text
    assert len(parsed.tables) == 1
    assert "매출" in parsed.tables[0].text

    split = split_clauses(parsed.text)
    assert split.style == "article"
    assert len(split.clauses) == 2
    assert split.clauses[0].title == "목적"
    assert split.clauses[0].text == "본 계약의 목적을 정한다."


def test_pasted_text_preserves_clause_line_boundaries():
    parsed = parse_pasted_text("제1조 (목적)\r\n본문 A\r\n제2조 (정산)\r\n본문 B")
    split = split_clauses(parsed.text)
    assert len(split.clauses) == 2
    assert split.clauses[1].text == "본문 B"


@pytest.mark.parametrize("filename", ["a.pdf", "a.docx", "a.hwp", "a.png"])
def test_required_file_types_are_accepted(filename):
    def handler(request: httpx.Request):
        return httpx.Response(200, request=request, json=_payload())

    parser = UpstageDocumentParser(
        "test-key", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert parser.parse_file(filename, b"content").text


def test_unsupported_extension_is_rejected_without_api_call():
    parser = UpstageDocumentParser("test-key")
    with pytest.raises(UnsupportedDocumentError):
        parser.parse_file("contract.exe", b"content")


def test_timeout_is_reported_without_document_content():
    def handler(request: httpx.Request):
        raise httpx.ReadTimeout("timeout", request=request)

    parser = UpstageDocumentParser(
        "test-key", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(DocumentParseTimeout) as exc:
        parser.parse_file("contract.pdf", b"SECRET CONTRACT TEXT")
    assert "SECRET" not in str(exc.value)


def test_http_error_does_not_expose_provider_body():
    def handler(request: httpx.Request):
        return httpx.Response(
            500,
            request=request,
            text="provider echoed SECRET CONTRACT TEXT",
        )

    parser = UpstageDocumentParser(
        "test-key", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(DocumentParseError) as exc:
        parser.parse_file("contract.pdf", b"SECRET CONTRACT TEXT")
    assert "HTTP 500" in str(exc.value)
    assert "SECRET" not in str(exc.value)


def test_empty_success_payload_is_not_treated_as_success():
    def handler(request: httpx.Request):
        return httpx.Response(200, request=request, json={"content": {}, "elements": []})

    parser = UpstageDocumentParser(
        "test-key", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(DocumentParseError):
        parser.parse_file("contract.pdf", b"content")
