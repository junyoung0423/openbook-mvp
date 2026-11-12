"""수동 확인용: python -m openbook.clauses <계약서.txt>"""

import sys
from pathlib import Path

from openbook.clauses.splitter import split_clauses


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("사용법: python -m openbook.clauses <계약서.txt>")
    out = split_clauses(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(f"형식={out.style} 조항={len(out.clauses)}개 LLM보완필요={out.needs_llm}")
    for w in out.warnings:
        print("경고:", w)
    for c in out.clauses:
        print(f"{c.id}  {c.no}  {c.title}  ({len(c.text)}자)")


if __name__ == "__main__":
    main()
