"""수동 확인용: python -m openbook.terms <계약서.txt>  (UPSTAGE_API_KEY 필요, 계약서가 Upstage로 전송됨)"""

import sys
from pathlib import Path

from openbook.clauses import split_clauses
from openbook.terms import UpstageClient, extract_terms


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("사용법: python -m openbook.terms <계약서.txt>")
    split = split_clauses(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if not split.clauses:
        sys.exit("조항을 나누지 못했습니다. (조항 분할 단계에서 LLM 보완이 필요한 문서)")
    result = extract_terms("cli", split.clauses, UpstageClient.from_env())
    for t in result.terms.terms:
        value = "-" if t.value is None else t.value
        print(f"{t.key.value:18} {t.status.value:10} {value}  [{t.source_clause_id or ''}]")
    for w in result.warnings:
        print("경고:", w)


if __name__ == "__main__":
    main()
