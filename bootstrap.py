#!/usr/bin/env python
"""전체 서비스 부트스트랩 스크립트.

원칙:
- DB/테이블 초기화 로직은 `bootstrap/` 하위 스크립트에만 둔다.
- 이 파일은 오케스트레이션(의존성 설치, 서버 실행/종료)만 담당한다.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from collections.abc import Iterable
from pathlib import Path
from typing import IO

from bootstrap._bootstrap_common import resolve_command

ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
FARMOS_BACKEND_DIR = ROOT / "backend"
SHOP_BACKEND_DIR = ROOT / "shopping_mall" / "backend"
FARMOS_FRONTEND_DIR = ROOT / "frontend"
SHOP_FRONTEND_DIR = ROOT / "shopping_mall" / "frontend"
PORTS = [8000, 4000, 5173, 5174]


class BootstrapError(RuntimeError):
    """부트스트랩 실패를 표현하는 예외."""


def info(message: str) -> None:
    print(f"[Bootstrap] {message}")


def fail(message: str, code: int = 1) -> None:
    print(f"[Bootstrap] ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def run_command(
    command: list[str],
    cwd: Path | None = None,
    check: bool = True,
    log_file: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    resolved = resolve_command(command)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("w", encoding="utf-8") as handle:
            result = subprocess.run(
                resolved,
                cwd=str(cwd) if cwd else None,
                text=True,
                stdout=handle,
                stderr=subprocess.STDOUT,
            )
    else:
        result = subprocess.run(
            resolved,
            cwd=str(cwd) if cwd else None,
            text=True,
        )
    if check and result.returncode != 0:
        raise BootstrapError(
            f"명령 실행 실패({result.returncode}): {' '.join(command)}"
        )
    return result


def check_required_tools() -> None:
    missing = [
        tool for tool in ("python", "npm", "uv", "psql") if shutil.which(tool) is None
    ]
    if missing:
        raise BootstrapError(f"필수 도구가 PATH에 없습니다: {', '.join(missing)}")


def ensure_uv_project(project_dir: Path, label: str, log_name: str) -> None:
    if not (project_dir / "pyproject.toml").exists():
        raise BootstrapError(f"{label}: pyproject.toml 누락 ({project_dir})")
    info(f"{label}: uv sync 실행")
    run_command(["uv", "sync"], cwd=project_dir, log_file=LOG_DIR / log_name)


def ensure_npm_project(project_dir: Path, label: str, log_name: str) -> None:
    if not (project_dir / "package.json").exists():
        raise BootstrapError(f"{label}: package.json 누락 ({project_dir})")
    if (project_dir / "node_modules").exists():
        info(f"{label}: node_modules 존재 (npm install 생략)")
        return
    info(f"{label}: npm install 실행")
    run_command(["npm", "install"], cwd=project_dir, log_file=LOG_DIR / log_name)


def ensure_databases() -> None:
    """DB/테이블 점검 및 필요 시 초기화를 `bootstrap/` 하위에 위임한다."""
    info("ShoppingMall DB 점검/초기화")
    run_command(
        [
            "python",
            str(Path("bootstrap") / "shoppingmall.py"),
            "--mode",
            "ensure",
            "--skip-sync",
        ],
        cwd=ROOT,
    )
    info("FarmOS DB 점검/초기화")
    run_command(
        [
            "python",
            str(Path("bootstrap") / "farmos.py"),
            "--mode",
            "ensure",
            "--skip-sync",
        ],
        cwd=ROOT,
    )


def start_service(
    name: str,
    command: Iterable[str],
    cwd: Path,
    log_name: str,
) -> tuple[str, subprocess.Popen[bytes], IO[str]]:
    log_path = LOG_DIR / log_name
    log_handle = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        resolve_command(list(command)),
        cwd=str(cwd),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
    )
    info(f"시작됨: {name} (PID={proc.pid})")
    return name, proc, log_handle


def stop_process_tree(pid: int) -> None:
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def pids_from_port(port: int) -> list[int]:
    result = subprocess.run(
        ["netstat", "-ano"],
        text=True,
        capture_output=True,
        check=False,
    )
    pids = set()
    if not result.stdout:
        return []
    marker = f":{port}"
    for line in result.stdout.splitlines():
        if marker not in line or "LISTENING" not in line:
            continue
        parts = line.split()
        if len(parts) >= 5 and parts[1].rsplit(":", 1)[-1] == str(port) and parts[-1].isdigit():
            pids.add(int(parts[-1]))
    return sorted(pids)


def stop_services(services: list[tuple[str, subprocess.Popen[bytes], IO[str]]]) -> None:
    info("서비스 종료 중...")
    for name, proc, log_handle in services:
        if proc.poll() is None:
            info(f"종료: {name} (PID={proc.pid})")
            stop_process_tree(proc.pid)
        log_handle.close()
    for port in PORTS:
        for pid in pids_from_port(port):
            stop_process_tree(pid)
    # subprocess.run(
    #     ["taskkill", "/F", "/IM", "node.exe"],
    #     stdout=subprocess.DEVNULL,
    #     stderr=subprocess.DEVNULL,
    #     check=False,
    # )


def run() -> None:
    os.chdir(ROOT)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    info("FarmOS 통합 부트스트랩 시작")
    info("FarmOS Backend   : http://localhost:8000")
    info("FarmOS Frontend  : http://localhost:5173")
    info("Shop Backend     : http://localhost:4000")
    info("Shop Frontend    : http://localhost:5174")

    check_required_tools()
    ensure_databases()

    ensure_uv_project(FARMOS_BACKEND_DIR, "FarmOS Backend", "farmos-be-setup.log")
    ensure_uv_project(SHOP_BACKEND_DIR, "Shop Backend", "shop-be-setup.log")
    ensure_npm_project(FARMOS_FRONTEND_DIR, "FarmOS Frontend", "farmos-fe-install.log")
    ensure_npm_project(SHOP_FRONTEND_DIR, "Shop Frontend", "shop-fe-install.log")

    services: list[tuple[str, subprocess.Popen[bytes], IO[str]]] = []
    try:
        services.append(
            start_service(
                "FarmOS Backend",
                ["uv", "run", "main.py"],
                FARMOS_BACKEND_DIR,
                "farmos-be.log",
            )
        )
        services.append(
            start_service(
                "Shop Backend",
                ["uv", "run", "main.py"],
                SHOP_BACKEND_DIR,
                "shop-be.log",
            )
        )
        time.sleep(3)
        services.append(
            start_service(
                "FarmOS Frontend",
                ["npm", "run", "dev"],
                FARMOS_FRONTEND_DIR,
                "farmos-fe.log",
            )
        )
        services.append(
            start_service(
                "Shop Frontend", ["npm", "run", "dev"], SHOP_FRONTEND_DIR, "shop-fe.log"
            )
        )
        print("\n모든 서비스가 실행되었습니다. 종료하려면 x/q/exit 입력 후 Enter.")
        while True:
            try:
                user_input = input("> ")
            except EOFError:
                info("표준 입력이 닫혀 서비스를 종료합니다.")
                break
            command = user_input.strip().lower()
            if command in {"x", "q", "exit", "quit"}:
                break
            if command == "":
                print("종료하려면 x/q/exit 를 입력하세요.")
    finally:
        stop_services(services)
        print("모든 서비스를 종료했습니다.")


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n사용자 인터럽트로 종료합니다.")
        raise SystemExit(130) from None
    except BootstrapError as exc:
        fail(str(exc))
