"""정산서 입력 정규화 (정준영). 표 붙여넣기를 StatementDraft로 바꾼다. LLM을 쓰지 않는다."""

from openbook.statements.paste import MAX_CHARS, parse_pasted_statement

__all__ = ["MAX_CHARS", "parse_pasted_statement"]
