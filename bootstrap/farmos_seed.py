#!/usr/bin/env python
# ruff: noqa: E402
# pyright: reportMissingImports=false, reportMissingModuleSource=false
"""FarmOS 스키마 생성 + 기본 계정 시드 스크립트.

모드:
- seed: 시드만 수행
- init: 항상 점검/초기화 수행
- ensure: 필요할 때만 점검/초기화 수행
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

from _bootstrap_common import (  # type: ignore[import-not-found]
    BootstrapError,
    detect_database_url,
    ensure_database_exists,
    ensure_postgres_running,
    ensure_tools,
    error,
    info,
    parse_database_url,
    print_table_summary,
    psql_query,
    run_command,
    set_log_prefix,
    table_exists,
)
from sqlalchemy import select, text

# 실행 위치와 무관하게 backend 패키지를 import 할 수 있도록 경로를 보정한다.
ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Base.metadata 등록을 위해 모델 모듈을 명시적으로 import 한다.
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

CORE_SUMMARY_TABLES = [
    "journal_entries",
    "review_analyses",
    "review_sentiments",
    "users",
]
POST_PESTICIDE_TABLES = [
    "rag_pesticide_crops",
    "rag_pesticide_documents",
    "rag_pesticide_product_applications",
    "rag_pesticide_products",
    "rag_pesticide_targets",
]
SUMMARY_TABLES = [*CORE_SUMMARY_TABLES, *POST_PESTICIDE_TABLES]
EXPECTED_ROW_COUNTS = {"users": 2}
POST_PESTICIDE_MIN_ROW_COUNTS = {
    "rag_pesticide_products": 1,
    "rag_pesticide_product_applications": 1,
    "rag_pesticide_documents": 1,
}
LOG_PREFIX = "FarmOS-S"


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
        for table in CORE_SUMMARY_TABLES:
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


def _to_asyncpg_url(raw_db_url: str) -> str:
    if raw_db_url.startswith("postgres://"):
        return raw_db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    url = re.sub(r"^postgresql\+\w+://", "postgresql+asyncpg://", raw_db_url, count=1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def uv_sync_backend(skip_sync: bool) -> None:
    if skip_sync:
        info("uv sync 생략 (--skip-sync)")
        return
    info("FarmOS backend 의존성 동기화(uv sync) - 시간이 많이 걸릴 수 있습니다")
    run_command(["uv", "sync"], cwd=BACKEND_DIR)


def all_farmos_tables_exist(db_conf: dict[str, str]) -> bool:
    return all(table_exists(db_conf, table) for table in CORE_SUMMARY_TABLES)


def all_post_pesticide_tables_exist(db_conf: dict[str, str]) -> bool:
    return all(table_exists(db_conf, table) for table in POST_PESTICIDE_TABLES)


def is_post_pesticide_ready(db_conf: dict[str, str]) -> bool:
    if not all_post_pesticide_tables_exist(db_conf):
        return False
    for table, expected_min in POST_PESTICIDE_MIN_ROW_COUNTS.items():
        actual = int(psql_query(db_conf, f"SELECT COUNT(*) FROM {table};") or "0")
        if actual < expected_min:
            return False
    return True


def drop_farmos_tables(db_conf: dict[str, str]) -> None:
    info("FarmOS 스키마 재구성: 기존 테이블 삭제(drop)")
    targets = [*SUMMARY_TABLES, "pesticide_products"]
    quoted_targets = ", ".join(_quote_identifier(table) for table in targets)
    psql_query(db_conf, f"DROP TABLE IF EXISTS {quoted_targets} CASCADE;")


def truncate_farmos_tables(db_conf: dict[str, str]) -> None:
    candidate_tables = [*SUMMARY_TABLES, "pesticide_products"]
    existing_tables = [
        table for table in candidate_tables if table_exists(db_conf, table)
    ]
    if not existing_tables:
        info("truncate 대상 FarmOS 테이블이 없습니다.")
        return
    info("FarmOS 데이터 비우기(truncate)")
    targets = ", ".join(_quote_identifier(table) for table in existing_tables)
    truncate_sql = (
        "BEGIN; "
        "SET LOCAL lock_timeout = '5s'; "
        f"TRUNCATE TABLE {targets} RESTART IDENTITY CASCADE; "
        "COMMIT;"
    )
    psql_query(db_conf, truncate_sql)


def is_farmos_ready(db_conf: dict[str, str]) -> bool:
    for table in CORE_SUMMARY_TABLES:
        if not table_exists(db_conf, table):
            return False
    for table, expected in EXPECTED_ROW_COUNTS.items():
        actual = int(psql_query(db_conf, f"SELECT COUNT(*) FROM {table};") or "0")
        if actual < expected:
            return False
    return True


def run_seed_pipeline(raw_db_url: str) -> None:
    info("FarmOS 코어 시드 실행")
    seed_script = ROOT / "bootstrap" / "farmos_seed.py"
    run_command(
        ["uv", "run", "python", str(seed_script), "--mode", "seed"],
        cwd=BACKEND_DIR,
        env_overrides={"DATABASE_URL": _to_asyncpg_url(raw_db_url)},
    )


def run_pesticide_loader(raw_db_url: str, append_mode: bool = True) -> None:
    info("농약 RAG 테이블 적재 스크립트 실행")
    loader_script = ROOT / "bootstrap" / "pesticide.py"
    json_dir = ROOT / "tools" / "api-crawler" / "json_raw"
    command = [
        "--db-url",
        raw_db_url,
        "--input-dir",
        str(json_dir),
    ]
    if append_mode:
        command.append("--append")
    venv_python = (
        BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
        if os.name == "nt"
        else BACKEND_DIR / ".venv" / "bin" / "python"
    )
    if venv_python.exists():
        run_command([str(venv_python), str(loader_script), *command], cwd=BACKEND_DIR)
        return
    run_command(["uv", "run", "python", str(loader_script), *command], cwd=BACKEND_DIR)


def print_db_summary(db_conf: dict[str, str], verbose_table_info: bool) -> None:
    print_table_summary(
        db_conf,
        "FarmOS (코어)",
        CORE_SUMMARY_TABLES,
        verbose_table_info=verbose_table_info,
    )
    print_table_summary(
        db_conf,
        "FarmOS (농약 RAG)",
        POST_PESTICIDE_TABLES,
        verbose_table_info=verbose_table_info,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="FarmOS 시드/초기화 스크립트")
    parser.add_argument("--database-url", help="DATABASE_URL 강제 지정")
    parser.add_argument("--skip-sync", action="store_true", help="uv sync 생략")
    parser.add_argument(
        "--mode",
        choices=("seed", "init", "ensure"),
        default="init",
        help="seed=시드만 실행, init=항상 초기화, ensure=필요 시 초기화",
    )
    parser.add_argument(
        "--rebuild-schema",
        action="store_true",
        help="초기화 시 스키마를 강제 재생성(drop/create)합니다.",
    )
    parser.add_argument(
        "--verbose-table-info",
        action="store_true",
        help="DB 요약에 테이블 컬럼/row 수 상세 정보를 출력합니다.",
    )
    args = parser.parse_args()

    set_log_prefix(LOG_PREFIX)
    try:
        if args.mode == "seed":
            return asyncio.run(run())

        ensure_tools("uv", "psql")
        raw_db_url = detect_database_url(args.database_url, prefer="farmos")
        db_conf = parse_database_url(raw_db_url)
        ensure_postgres_running(db_conf)
        ensure_database_exists(db_conf)

        initialized = args.mode == "init"
        did_sync = False
        if args.mode == "ensure":
            force_pesticide_reload = False
            if args.rebuild_schema:
                info("사용자 요청으로 강제 초기화 수행 (--rebuild-schema)")
                uv_sync_backend(args.skip_sync)
                did_sync = True
                drop_farmos_tables(db_conf)
                run_seed_pipeline(raw_db_url)
                force_pesticide_reload = True
                initialized = True
            elif is_farmos_ready(db_conf):
                info("FarmOS DB 상태 정상 (초기화 생략)")
            else:
                info("FarmOS DB 상태 불완전 (초기화 수행)")
                uv_sync_backend(args.skip_sync)
                did_sync = True
                rebuild_schema = not all_farmos_tables_exist(db_conf)
                if rebuild_schema:
                    info("FarmOS 필수 테이블 일부 누락 감지 (스키마 재구성 모드)")
                    drop_farmos_tables(db_conf)
                else:
                    truncate_farmos_tables(db_conf)
                run_seed_pipeline(raw_db_url)
                initialized = True

            # 코어 초기화 여부와 무관하게 농약 테이블 상태를 항상 별도로 점검한다.
            if (not force_pesticide_reload) and is_post_pesticide_ready(db_conf):
                info("FarmOS 농약 RAG 테이블 상태 정상 (적재 생략)")
            else:
                info("FarmOS 농약 RAG 테이블 상태 불완전 (적재 수행)")
                if not did_sync:
                    uv_sync_backend(args.skip_sync)
                    did_sync = True
                run_pesticide_loader(
                    raw_db_url,
                    append_mode=(
                        (not force_pesticide_reload)
                        and all_post_pesticide_tables_exist(db_conf)
                    ),
                )
                initialized = True
        else:
            uv_sync_backend(args.skip_sync)
            rebuild_schema = args.rebuild_schema or (
                not all_farmos_tables_exist(db_conf)
            )
            if rebuild_schema:
                drop_farmos_tables(db_conf)
            else:
                truncate_farmos_tables(db_conf)
            run_seed_pipeline(raw_db_url)
            run_pesticide_loader(
                raw_db_url,
                append_mode=(
                    (not rebuild_schema) and all_post_pesticide_tables_exist(db_conf)
                ),
            )

        if initialized:
            print_db_summary(db_conf, args.verbose_table_info)
            print()
            info("FarmOS 데이터베이스 초기화 완료")
        else:
            info("FarmOS 데이터베이스 상태 확인 완료")
        return 0
    except BootstrapError as exc:
        error(str(exc))
        return 1
    except Exception as exc:
        error(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
