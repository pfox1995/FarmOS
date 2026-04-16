#!/usr/bin/env python
# ruff: noqa: E402
# pyright: reportMissingImports=false, reportMissingModuleSource=false
"""FarmOS 스키마 생성 + 기본 계정 시드 스크립트.

이 파일은 `bootstrap/farmos.py`에서 호출된다.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from _bootstrap_common import (  # type: ignore[import-not-found]
    error,
    info,
    set_log_prefix,
)
from sqlalchemy import select, text

# 실행 위치와 무관하게 backend 패키지를 import 할 수 있도록 경로를 보정한다.
ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Base.metadata 등록을 위해 모델 모듈을 명시적으로 import 한다.
# NOTE: pesticide_products는 제거 대상이므로 여기서 import하지 않는다.
import app.models.journal  # noqa: F401
import app.models.review_analysis  # noqa: F401
from app.core.database import async_session, close_db, init_db
from app.core.security import hash_password
from app.models.user import User

# ======================
# 수정이 쉬운 상단 설정값
# ======================

USER_SEEDS = [
    {
        "id": "farmer01",
        "name": "김사과",
        "email": "farmer01@farmos.kr",
        "password": "farm1234",
        "location": "경북 영주시",
        "area": 33.0,
        "farmname": "김사과 사과농장",
        "profile": "",
    },
    {
        "id": "parkpear",
        "name": "박배나무",
        "email": "parkpear@farmos.kr",
        "password": "pear5678",
        "location": "충남 천안시",
        "area": 25.5,
        "farmname": "박씨네 배 과수원",
        "profile": "",
    },
]

SUMMARY_TABLES = [
    "users",
    "journal_entries",
    "review_analyses",
    "review_sentiments",
]

LOG_PREFIX = "FOS-SEED"


async def seed_users() -> None:
    """기본 테스트 계정을 upsert 방식으로 채운다."""
    async with async_session() as db:
        for data in USER_SEEDS:
            exists = await db.execute(select(User).where(User.id == data["id"]))
            if exists.scalar_one_or_none():
                continue
            db.add(
                User(
                    id=data["id"],
                    name=data["name"],
                    email=data["email"],
                    password=hash_password(data["password"]),
                    location=data["location"],
                    area=data["area"],
                    farmname=data["farmname"],
                    profile=data["profile"],
                )
            )
        await db.commit()


async def print_summary() -> None:
    """초기화 이후 핵심 테이블 row 수를 출력한다."""
    info("FarmOS 시드 요약")
    async with async_session() as db:
        for table in SUMMARY_TABLES:
            result = await db.execute(text(f"SELECT COUNT(*) FROM {table};"))
            count = result.scalar() or 0
            print(f"  - {table}: {count} rows")


async def run() -> int:
    info("FarmOS 스키마 생성 시작")
    await init_db()
    await seed_users()
    print()
    await print_summary()
    await close_db()
    print()
    info("FarmOS 시드 완료")
    return 0


if __name__ == "__main__":
    set_log_prefix(LOG_PREFIX)
    try:
        raise SystemExit(asyncio.run(run()))
    except Exception as exc:
        error(str(exc))
        raise
