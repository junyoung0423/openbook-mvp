class DocumentParseError(RuntimeError):
    """문서 파싱 실패. 메시지에는 원문이나 외부 응답 본문을 넣지 않는다."""


class DocumentParseConfigError(DocumentParseError):
    pass


class UnsupportedDocumentError(DocumentParseError):
    pass


class DocumentParseTimeout(DocumentParseError):
    pass
