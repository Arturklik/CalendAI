"""CalendAI backend — асинхронный FastAPI-сервис.

Монорепозиторий: пакет `ai_module` лежит в корне репозитория, рядом с
директорией `backend/`. Чтобы `import ai_module` работал при локальном
запуске из каталога backend/ (uvicorn app.main:app), добавляем корень
репозитория в sys.path. В Docker это делает PYTHONPATH (см. Dockerfile),
и данный bootstrap становится no-op.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

if (_REPO_ROOT / "ai_module").is_dir() and str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
