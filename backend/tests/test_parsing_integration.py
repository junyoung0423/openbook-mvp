import io
import os
import zipfile

import pytest

from openbook.clauses import split_clauses
from openbook.parsing import UpstageDocumentParser

RUN = os.getenv("RUN_UPSTAGE_INTEGRATION") == "1" and bool(os.getenv("UPSTAGE_API_KEY"))
pytestmark = pytest.mark.skipif(not RUN, reason="실제 Upstage 통합 테스트를 명시적으로 켜지 않음")


def _minimal_docx() -> bytes:
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>제1조 (목적)</w:t></w:r></w:p>
    <w:p><w:r><w:t>본 계약의 목적을 정한다.</w:t></w:r></w:p>
    <w:p><w:r><w:t>제2조 (정산)</w:t></w:r></w:p>
    <w:p><w:r><w:t>정산은 매월 실시한다.</w:t></w:r></w:p>
  </w:body>
</w:document>"""
    content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document_xml)
    return out.getvalue()


@pytest.mark.integration
def test_real_document_parse_output_can_feed_clause_splitter():
    parser = UpstageDocumentParser.from_env()
    parsed = parser.parse_file("sample.docx", _minimal_docx())
    split = split_clauses(parsed.text)
    assert split.style == "article"
    assert len(split.clauses) == 2
    assert split.clauses[0].title == "목적"
    assert split.clauses[1].title == "정산"
