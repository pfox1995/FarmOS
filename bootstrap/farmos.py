#!/usr/bin/env python
"""FarmOS DB/테이블 초기화 스크립트."""

from __future__ import annotations

import argparse
import os
import re

from _bootstrap_common import (  # type: ignore[import-not-found]
    BACKEND_DIR,
    ROOT,
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

FARMOS_TABLES = [
    "users",
    "journal_entries",
    "rag_pesticide_products",
    "rag_pesticide_crops",
    "rag_pesticide_targets",
    "rag_pesticide_product_applications",
    "rag_pesticide_documents",
    "review_analyses",
    "review_sentiments",
]
LOG_PREFIX = "FOS"
EXPECTED_ROW_COUNTS = {
    "users": 2,
}


def _to_asyncpg_url(raw_db_url: str) -> str:
    """driver 부분을 FarmOS 비동기 엔진용 URL로 맞춘다."""
    if raw_db_url.startswith("postgres://"):
        return raw_db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    url = re.sub(r"^postgresql\+\w+://", "postgresql+asyncpg://", raw_db_url, count=1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def uv_sync_backend(skip_sync: bool) -> None:
    if skip_sync:
        info("uv sync 생략 (--skip-sync)")
        return
    info("FarmOS backend 의존성 동기화(uv sync)")
    run_command(["uv", "sync"], cwd=BACKEND_DIR)


def drop_farmos_tables(db_conf: dict[str, str]) -> None:
    info("FarmOS 테이블 삭제(drop)")
    # legacy: 기존 mock 농약 캐시 테이블도 함께 제거
    targets = [*FARMOS_TABLES, "pesticide_products"]
    psql_query(db_conf, "DROP TABLE IF EXISTS " + ", ".join(targets) + " CASCADE;")


def run_farmos_seed(async_db_url: str) -> None:
    """실제 스키마 생성 + 기본 유저 시드를 farmos_seed.py에 위임한다."""
    info("FarmOS 스키마/시드 적용")
    seed_script = ROOT / "bootstrap" / "farmos_seed.py"
    run_command(
        ["uv", "run", "python", str(seed_script)],
        cwd=BACKEND_DIR,
        env_overrides={"DATABASE_URL": async_db_url},
    )


def run_pesticide_loader(raw_db_url: str) -> None:
    info("농약 RAG 테이블 적재 스크립트 실행")
    loader_script = ROOT / "bootstrap" / "pesticide.py"
    json_dir = ROOT / "tools" / "api-crawler" / "json_raw"
    command = [
        "--db-url",
        raw_db_url,
        "--input-dir",
        str(json_dir),
    ]
    venv_python = (
        BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
        if os.name == "nt"
        else BACKEND_DIR / ".venv" / "bin" / "python"
    )
    if venv_python.exists():
        run_command([str(venv_python), str(loader_script), *command], cwd=BACKEND_DIR)
        return
    run_command(["uv", "run", "python", str(loader_script), *command], cwd=BACKEND_DIR)


def is_farmos_ready(db_conf: dict[str, str]) -> bool:
    """운영에 필요한 최소 상태를 확인한다.

    기준:
    - 필수 테이블 존재
    - users 테이블에 테스트 계정 2명 이상 존재
    """
    for table in FARMOS_TABLES:
        if not table_exists(db_conf, table):
            return False
    for table, expected in EXPECTED_ROW_COUNTS.items():
        actual = int(psql_query(db_conf, f"SELECT COUNT(*) FROM {table};") or "0")
        if actual != expected:
            return False
    return True


def print_summary(db_conf: dict[str, str], verbose_table_info: bool) -> None:
    print_table_summary(
        db_conf,
        "FarmOS",
        FARMOS_TABLES,
        verbose_table_info=verbose_table_info,
    )


def initialize(db_conf: dict[str, str], raw_db_url: str, skip_sync: bool) -> None:
    uv_sync_backend(skip_sync)
    drop_farmos_tables(db_conf)
    run_farmos_seed(_to_asyncpg_url(raw_db_url))
    run_pesticide_loader(raw_db_url)


def main() -> int:
    parser = argparse.ArgumentParser(description="FarmOS PostgreSQL 초기화")
    parser.add_argument("--database-url", help="DATABASE_URL 강제 지정")
    parser.add_argument("--skip-sync", action="store_true", help="uv sync 생략")
    parser.add_argument(
        "--mode",
        choices=("init", "ensure"),
        default="init",
        help="init=항상 재초기화, ensure=필요할 때만 초기화",
    )
    parser.add_argument(
        "--verbose-table-info",
        action="store_true",
        help="테이블 컬럼/row 수 상세 정보를 출력",
    )
    args = parser.parse_args()

    try:
        set_log_prefix(LOG_PREFIX)
        ensure_tools("uv", "psql")
        raw_db_url = detect_database_url(args.database_url, prefer="farmos")
        db_conf = parse_database_url(raw_db_url)

        ensure_postgres_running(db_conf)
        ensure_database_exists(db_conf)

        initialized = args.mode == "init"
        if args.mode == "ensure":
            if is_farmos_ready(db_conf):
                info("FarmOS DB 상태 정상 (초기화 생략)")
            else:
                info("FarmOS DB 상태 불완전 (초기화 수행)")
                initialize(db_conf, raw_db_url, args.skip_sync)
                initialized = True
        else:
            initialize(db_conf, raw_db_url, args.skip_sync)
        if initialized:
            print_summary(db_conf, args.verbose_table_info)
            print()
            info("FarmOS 데이터베이스 초기화 완료")
        else:
            info("FarmOS 데이터베이스 상태 확인 완료")
        return 0
    except BootstrapError as exc:
        error(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
