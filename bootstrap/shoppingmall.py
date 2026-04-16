#!/usr/bin/env python
"""ShoppingMall DB/테이블 초기화 스크립트."""

from __future__ import annotations

import argparse
import re

from _bootstrap_common import (  # type: ignore[import-not-found]
    ROOT,
    SHOP_BACKEND_DIR,
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

SHOP_TABLES = [
    "shop_categories",
    "shop_stores",
    "shop_products",
    "shop_users",
    "shop_cart_items",
    "shop_orders",
    "shop_order_items",
    "shop_reviews",
    "shop_wishlists",
    "shop_shipments",
    "shop_harvest_schedules",
    "shop_revenue_entries",
    "shop_expense_entries",
    "shop_weekly_reports",
    "shop_customer_segments",
    "shop_chat_logs",
    "shop_chat_sessions",
]
LOG_PREFIX = "SHOP"


def uv_sync_backend(skip_sync: bool) -> None:
    if skip_sync:
        info("uv sync 생략 (--skip-sync)")
        return
    info("shopping_mall/backend 의존성 동기화(uv sync)")
    run_command(["uv", "sync"], cwd=SHOP_BACKEND_DIR)


def drop_shop_tables(db_conf: dict[str, str]) -> None:
    existing = psql_query(
        db_conf,
        "SELECT tablename FROM pg_tables "
        "WHERE schemaname='public' AND tablename LIKE 'shop_%' "
        "ORDER BY tablename;",
    )
    table_names = [line.strip() for line in existing.splitlines() if line.strip()]
    if not table_names:
        info("기존 shop_* 테이블이 없습니다.")
        return

    info("기존 shop_* 테이블 삭제(drop)")
    drop_sql = "DROP TABLE IF EXISTS " + ", ".join(table_names) + " CASCADE;"
    psql_query(db_conf, drop_sql)


def run_seed_pipeline(raw_db_url: str) -> None:
    info("통합 쇼핑몰 시드 스크립트 실행")
    seed_script = ROOT / "bootstrap" / "shoppingmall_seed.py"
    run_command(
        ["uv", "run", "python", str(seed_script)],
        cwd=SHOP_BACKEND_DIR,
        env_overrides={"DATABASE_URL": _to_sync_db_url(raw_db_url)},
    )


def run_review_seed_pipeline(raw_db_url: str) -> None:
    info("쇼핑몰 리뷰 시드 스크립트 실행")
    review_seed = ROOT / "bootstrap" / "shoppingmall_review_seed.py"
    run_command(
        ["uv", "run", "python", str(review_seed)],
        cwd=SHOP_BACKEND_DIR,
        env_overrides={"DATABASE_URL": _to_sync_db_url(raw_db_url)},
    )


def _to_sync_db_url(raw_db_url: str) -> str:
    # shopping_mall backend는 동기 SQLAlchemy(psycopg2) 드라이버를 사용한다.
    url = re.sub(r"^postgresql\+\w+://", "postgresql+psycopg2://", raw_db_url, count=1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def print_summary(db_conf: dict[str, str], verbose_table_info: bool) -> None:
    print_table_summary(
        db_conf,
        "ShoppingMall",
        SHOP_TABLES,
        verbose_table_info=verbose_table_info,
    )


def is_shoppingmall_ready(db_conf: dict[str, str]) -> bool:
    """shop_* 필수 테이블 존재 및 기대 row 수 일치 여부를 확인한다."""
    expected = {
        "shop_cart_items": 5,
        "shop_categories": 12,
        "shop_chat_logs": 5,
        "shop_chat_sessions": 0,
        "shop_customer_segments": 5,
        "shop_expense_entries": 10,
        "shop_harvest_schedules": 8,
        "shop_order_items": 19,
        "shop_orders": 10,
        "shop_products": 42,
        "shop_revenue_entries": 15,
        "shop_reviews": 1000,
        "shop_shipments": 5,
        "shop_stores": 5,
        "shop_users": 5,
        "shop_weekly_reports": 2,
        "shop_wishlists": 8,
    }
    for table, count in expected.items():
        if not table_exists(db_conf, table):
            return False
        actual = int(psql_query(db_conf, f"SELECT COUNT(*) FROM {table};") or "0")
        if actual != count:
            return False
    return True


def initialize(db_conf: dict[str, str], raw_db_url: str, skip_sync: bool) -> None:
    uv_sync_backend(skip_sync)
    drop_shop_tables(db_conf)
    run_seed_pipeline(raw_db_url)
    run_review_seed_pipeline(raw_db_url)


def main() -> int:
    parser = argparse.ArgumentParser(description="ShoppingMall PostgreSQL 초기화")
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
        raw_db_url = detect_database_url(args.database_url, prefer="shoppingmall")
        db_conf = parse_database_url(raw_db_url)

        ensure_postgres_running(db_conf)
        ensure_database_exists(db_conf)
        initialized = args.mode == "init"
        if args.mode == "ensure":
            if is_shoppingmall_ready(db_conf):
                info("ShoppingMall DB 상태 정상 (초기화 생략)")
            else:
                info("ShoppingMall DB 상태 불완전 (초기화 수행)")
                initialize(db_conf, raw_db_url, args.skip_sync)
                initialized = True
        else:
            initialize(db_conf, raw_db_url, args.skip_sync)
        if initialized:
            print_summary(db_conf, args.verbose_table_info)
            print()
            info("ShoppingMall 데이터베이스 초기화 완료")
        else:
            info("ShoppingMall 데이터베이스 상태 확인 완료")
        return 0
    except BootstrapError as exc:
        error(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
