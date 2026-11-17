"""공용 스키마를 JSON Schema 파일로 내보낸다. 프론트엔드는 이 파일로 타입을 만든다.

사용: python backend/scripts/export_json_schema.py
스키마(backend/src/openbook/schemas/)를 바꾼 PR에는 이 결과(docs/schemas/)도 함께 커밋한다.
"""

import json
from pathlib import Path

from openbook.schemas import ClauseSplitResult, termset_json_schema

OUT = Path(__file__).resolve().parents[2] / "docs" / "schemas"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    schemas = {
        "clauses": ClauseSplitResult.model_json_schema(),
        # Term.value의 key별 형식·선택값을 oneOf로 포함 (프론트 타입 생성용)
        "terms": termset_json_schema(),
    }
    for name, schema in schemas.items():
        path = OUT / f"{name}.schema.json"
        path.write_text(
            json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print("wrote", path)


if __name__ == "__main__":
    main()
