"""Vercel 배포 파일(저장소 루트의 app.py, requirements.txt, vercel.json)이 백엔드와 어긋나지 않는지."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _names(specs: list[str]) -> set[str]:
    return {re.split(r"[<>=\[ ]", s.strip(), maxsplit=1)[0].lower() for s in specs if s.strip()}


def test_requirements_match_pyproject_dependencies():
    project = tomllib.loads((ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8"))
    lines = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    reqs = [x for x in lines if x.strip() and not x.startswith("#")]
    assert sorted(reqs) == sorted(project["project"]["dependencies"])
    assert "fastapi" in _names(reqs)  # Vercel이 FastAPI로 알아보는 기준


def test_vercel_entrypoint_exposes_the_api_app():
    import runpy

    ns = runpy.run_path(str(ROOT / "app.py"))
    from openbook.api.main import app

    assert ns["app"] is app


def test_vercel_function_config_keeps_runtime_data():
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    fn = config["functions"]["app.py"]
    assert fn["maxDuration"] <= 300  # Hobby 최대
    excluded = fn["excludeFiles"]
    for needed in ("data/law", "data/standard", "backend/src"):  # 실행 중에 읽는 파일
        assert needed not in excluded
