"""Vercel 진입점 (FastAPI). Vercel은 저장소 루트의 app.py에서 `app`을 찾는다.

백엔드 패키지는 backend/src에 있어서 설치하지 않고 경로만 더한다. 그래야 패키지 파일 기준 경로
(data/law/index.json, data/standard/)가 저장소 그대로 맞는다. 의존성은 루트 requirements.txt.
로컬 개발은 지금처럼 backend/에서 uvicorn openbook.api.main:app을 쓴다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend" / "src"))

from openbook.api.main import app  # noqa: E402

__all__ = ["app"]
