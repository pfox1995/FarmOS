"""프로젝트 경로 상수 모음.

모든 경로는 이 모듈에서 중앙 관리합니다.
다른 모듈에서 os.path / __file__ 기반 경로를 직접 계산하지 마세요.
"""
from pathlib import Path

# shopping_mall/backend/app/
APP_DIR = Path(__file__).parent

# shopping_mall/backend/
BACKEND_ROOT = APP_DIR.parent

# shopping_mall/backend/ai/
AI_DIR = BACKEND_ROOT / "ai"

# FarmOS/  (프로젝트 최상위)
PROJECT_ROOT = BACKEND_ROOT.parent.parent

# FarmOS/logs/
LOG_DIR = PROJECT_ROOT / "logs"

# shopping_mall/backend/chroma_data/
CHROMA_DB_PATH = str(BACKEND_ROOT / "chroma_data")

# shopping_mall/backend/ai/data/
AI_DATA_DIR = AI_DIR / "data"

# shopping_mall/backend/ai/docs/  (정책 문서 — gitignore 처리, 로컬에 PDF/DOCX 배치)
POLICY_DOCS_DIR = AI_DIR / "docs"
