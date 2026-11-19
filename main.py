"""저장소의 기본 실행점: 통합 쇼핑몰 백엔드를 실행합니다."""

import sys
from pathlib import Path

backend_dir = str(Path(__file__).resolve().parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app

__all__ = ["app"]
