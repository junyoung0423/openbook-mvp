"""표준계약서 불러오기. 파일 형식은 data/standard/README.md를 따른다."""

from __future__ import annotations

from pathlib import Path

import yaml

from openbook.comparison.models import StandardClause


def load_standard(path: str | Path) -> list[StandardClause]:
    """YAML 또는 JSON 파일(조항 목록)에서 표준계약서를 읽는다. id가 중복되면 오류."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))  # JSON도 YAML의 부분집합
    items = data["clauses"] if isinstance(data, dict) else data
    clauses = [StandardClause.model_validate(it) for it in items]
    ids = [c.id for c in clauses]
    if len(ids) != len(set(ids)):
        raise ValueError("표준계약서 조항 id가 중복되었습니다.")
    return clauses
