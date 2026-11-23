"""표준계약서 불러오기. 파일 형식은 data/standard/README.md를 따른다."""

from __future__ import annotations

from pathlib import Path

import yaml

from openbook.comparison.models import StandardClause

# 기본 표준계약서: 만화 분야 표준계약서 [별표 3] 웹툰 연재계약서 (출처는 data/standard/SOURCE.md)
DEFAULT_STANDARD = (
    Path(__file__).resolve().parents[4] / "data" / "standard" / "webtoon_serial_2024.yaml"
)


def load_standard(
    path: str | Path = DEFAULT_STANDARD, *, core_only: bool = False
) -> list[StandardClause]:
    """YAML 또는 JSON 파일(조항 목록)에서 표준계약서를 읽는다. id가 중복되면 오류.

    core_only=True면 core로 표시한 조항(MVP에서 비교하는 정산 관련 조항)만 돌려준다.
    """
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))  # JSON도 YAML의 부분집합
    items = data["clauses"] if isinstance(data, dict) else data
    # YAML 1.1은 따옴표 없는 키 no를 False로 읽는다. 조항 번호가 사라지지 않게 되돌린다.
    items = [{("no" if k is False else k): v for k, v in it.items()} for it in items]
    clauses = [StandardClause.model_validate(it) for it in items]
    ids = [c.id for c in clauses]
    if len(ids) != len(set(ids)):
        raise ValueError("표준계약서 조항 id가 중복되었습니다.")
    return [c for c in clauses if c.core] if core_only else clauses
