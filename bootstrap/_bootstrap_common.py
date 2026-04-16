from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
SHOP_BACKEND_DIR = ROOT / "shopping_mall" / "backend"


class BootstrapError(RuntimeError):
    """부트스트랩 공통 예외."""


ROOT_LOG_PREFIX = "Bootstrap"
LOG_PREFIX_WIDTH = 10
_current_log_prefix = ROOT_LOG_PREFIX


def set_log_prefix(prefix: str) -> None:
    global _current_log_prefix
    _current_log_prefix = prefix.strip() or ROOT_LOG_PREFIX


def _format_log_prefix(prefix: str) -> str:
    if prefix == ROOT_LOG_PREFIX:
        return ROOT_LOG_PREFIX
    return prefix.ljust(LOG_PREFIX_WIDTH)


def info(message: str) -> None:
    print(f"[{_format_log_prefix(_current_log_prefix)}] {message}")


def error(message: str) -> None:
    print(
        f"[{_format_log_prefix(_current_log_prefix)}] 오류: {message}", file=sys.stderr
    )


def _sql_literal(value: str) -> str:
    """SQL 문자열 리터럴을 안전하게 이스케이프한다."""
    return "'" + value.replace("'", "''") + "'"


def _sql_identifier(name: str) -> str:
    """SQL 식별자를 안전하게 이스케이프한다."""
    if not name:
        raise BootstrapError("식별자(identifier)는 비어 있을 수 없습니다.")
    return '"' + name.replace('"', '""') + '"'


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def normalize_db_url(db_url: str) -> str:
    return re.sub(r"^postgresql\+\w+://", "postgresql://", db_url, count=1)


def parse_database_url(db_url: str) -> dict[str, str]:
    parsed = urlparse(normalize_db_url(db_url))
    if parsed.scheme != "postgresql":
        raise BootstrapError(f"지원하지 않는 DATABASE_URL 스킴입니다: {parsed.scheme}")
    if not parsed.hostname or not parsed.username:
        raise BootstrapError("DATABASE_URL에는 host와 username이 포함되어야 합니다.")

    return {
        "host": parsed.hostname,
        "port": str(parsed.port or 5432),
        "user": parsed.username,
        "password": parsed.password or "",
        "database": (parsed.path or "/farmos").lstrip("/") or "farmos",
    }


def detect_database_url(
    explicit_url: str | None = None, prefer: str = "shoppingmall"
) -> str:
    """DATABASE_URL을 우선순위에 따라 탐색한다."""
    if explicit_url:
        return explicit_url

    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]

    if prefer == "farmos":
        env_candidates = [BACKEND_DIR / ".env", SHOP_BACKEND_DIR / ".env"]
    else:
        env_candidates = [SHOP_BACKEND_DIR / ".env", BACKEND_DIR / ".env"]

    for env_file in env_candidates:
        env_map = load_dotenv(env_file)
        if env_map.get("DATABASE_URL"):
            return env_map["DATABASE_URL"]

    return "postgresql+psycopg2://postgres:root@localhost:5432/farmos"


def resolve_command(command: list[str]) -> list[str]:
    """Windows의 cmd/bat 실행을 안전하게 보정한다."""
    if not command:
        raise BootstrapError("빈 명령은 허용되지 않습니다.")

    executable = command[0]
    resolved = shutil.which(executable) or executable
    suffix = Path(resolved).suffix.lower()
    if os.name == "nt" and suffix in {".cmd", ".bat"}:
        comspec = os.environ.get("COMSPEC", "cmd.exe")
        return [comspec, "/c", resolved, *command[1:]]
    return [resolved, *command[1:]]


def run_command(
    command: list[str],
    cwd: Path | None = None,
    env_overrides: dict[str, str] | None = None,
    check: bool = True,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    resolved = resolve_command(command)
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)

    result = subprocess.run(
        resolved,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=capture_output,
        check=False,
    )
    if check and result.returncode != 0:
        raise BootstrapError(
            f"명령 실행 실패({result.returncode}): {' '.join(command)}"
        )
    return result


def ensure_tools(*tools: str) -> None:
    missing: list[str] = []
    for tool in tools:
        if tool == "psql":
            if resolve_psql_executable() is None:
                missing.append(tool)
            continue
        if shutil.which(tool) is None:
            missing.append(tool)
    if missing:
        raise BootstrapError(
            f"필수 도구를 PATH에서 찾을 수 없습니다: {', '.join(missing)}"
        )


@lru_cache(maxsize=1)
def resolve_psql_executable() -> str | None:
    """psql 실행 파일 경로를 탐색한다.

    우선순위:
    1) PSQL_EXE 환경변수
    2) PATH의 psql
    3) (Windows) 일반 PostgreSQL 설치 경로 탐색
    """
    explicit = os.getenv("PSQL_EXE")
    if explicit and Path(explicit).exists():
        return explicit

    from_path = shutil.which("psql")
    if from_path:
        return from_path

    if os.name != "nt":
        return None

    windows_candidates: list[Path] = []
    pghome = os.getenv("PGHOME")
    if pghome:
        windows_candidates.append(Path(pghome) / "bin" / "psql.exe")

    pg_bin = os.getenv("PG_BIN")
    if pg_bin:
        windows_candidates.append(Path(pg_bin) / "psql.exe")

    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.getenv(env_name)
        if not base:
            continue
        root = Path(base) / "PostgreSQL"
        if not root.exists():
            continue
        windows_candidates.extend(sorted(root.glob("*/bin/psql.exe"), reverse=True))

    for candidate in windows_candidates:
        if candidate.exists():
            return str(candidate)
    return None


def ensure_postgres_running(db_conf: dict[str, str]) -> None:
    info(f"PostgreSQL 서버 연결 확인 중 ({db_conf['host']}:{db_conf['port']})...")
    try:
        with socket.create_connection(
            (db_conf["host"], int(db_conf["port"])), timeout=2
        ):
            pass
    except OSError as exc:
        raise BootstrapError(f"PostgreSQL 서버에 연결할 수 없습니다: {exc}") from exc

    probe = psql_query(db_conf, "SELECT 1;", database="postgres")
    if probe != "1":
        raise BootstrapError("SELECT 1 쿼리로 PostgreSQL 연결 검증에 실패했습니다.")


def psql_query(db_conf: dict[str, str], sql: str, database: str | None = None) -> str:
    psql_executable = resolve_psql_executable()
    if psql_executable is None:
        raise BootstrapError(
            "psql 실행 파일을 찾을 수 없습니다. "
            "PostgreSQL의 'bin' 디렉터리를 PATH에 추가하거나 PSQL_EXE 환경변수를 설정하세요."
        )
    target_db = database or db_conf["database"]
    result = run_command(
        [
            psql_executable,
            "-h",
            db_conf["host"],
            "-p",
            db_conf["port"],
            "-U",
            db_conf["user"],
            "-d",
            target_db,
            "-tA",
            "-c",
            sql,
        ],
        env_overrides={"PGPASSWORD": db_conf["password"]},
        capture_output=True,
    )
    return (result.stdout or "").strip()


def ensure_database_exists(db_conf: dict[str, str]) -> None:
    db_name = db_conf["database"]
    exists = psql_query(
        db_conf,
        f"SELECT 1 FROM pg_database WHERE datname = {_sql_literal(db_name)};",
        database="postgres",
    )
    if exists == "1":
        return
    info(f"데이터베이스 '{db_name}'가 없어 새로 생성합니다.")
    psql_query(
        db_conf, f"CREATE DATABASE {_sql_identifier(db_name)};", database="postgres"
    )


def table_exists(db_conf: dict[str, str], table_name: str) -> bool:
    out = psql_query(
        db_conf,
        "SELECT 1 FROM pg_tables "
        "WHERE schemaname='public' "
        f"AND tablename={_sql_literal(table_name)};",
    )
    return out == "1"


def describe_table_columns(
    db_conf: dict[str, str], table_name: str
) -> list[dict[str, str]]:
    output = psql_query(
        db_conf,
        "SELECT column_name, data_type, is_nullable, "
        "COALESCE(column_default, '') "
        "FROM information_schema.columns "
        f"WHERE table_schema='public' AND table_name={_sql_literal(table_name)} "
        "ORDER BY ordinal_position;",
    )
    columns: list[dict[str, str]] = []
    for line in output.splitlines():
        parts = line.split("|", 3)
        if len(parts) != 4:
            continue
        columns.append(
            {
                "name": parts[0].strip(),
                "type": parts[1].strip(),
                "nullable": parts[2].strip(),
                "default": parts[3].strip(),
            }
        )
    return columns


def print_table_summary(
    db_conf: dict[str, str],
    label: str,
    tables: list[str],
    verbose_table_info: bool = False,
) -> None:
    print()
    info(f"{label} 테이블 요약")
    if not verbose_table_info:
        for table in tables:
            print(f"  - {table}")
        return

    for table in tables:
        if not table_exists(db_conf, table):
            print(f"  - {table}: MISSING")
            continue
        count = psql_query(db_conf, f"SELECT COUNT(*) FROM {_sql_identifier(table)};")
        print(f"  - {table}: {count} rows")
        for column in describe_table_columns(db_conf, table):
            nullability = "NULL" if column["nullable"] == "YES" else "NOT NULL"
            default_part = f", default={column['default']}" if column["default"] else ""
            print(
                f"      - {column['name']}: {column['type']} "
                f"({nullability}{default_part})"
            )
