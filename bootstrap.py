#!/usr/bin/env python
"""전체 서비스 부트스트랩 스크립트.

원칙:
- DB/테이블 초기화 로직은 `bootstrap/` 하위 스크립트에만 둔다.
- 이 파일은 오케스트레이션(의존성 설치, 서버 실행/종료)만 담당한다.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass
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


@dataclass
class BootstrapOptions:
    """부트스트랩 실행 옵션."""

    verbose_table_info: bool = False


@dataclass
class ServiceProcess:
    """실행 중인 하위 서비스를 추적하기 위한 정보."""

    name: str
    process: subprocess.Popen[bytes]
    log_handle: IO[str]
    log_path: Path
    exit_reported: bool = False
    exit_code: int | None = None


@dataclass
class InputReaderController:
    """입력 스레드 제어 정보를 묶는다."""

    thread: threading.Thread
    prompt_request: threading.Event
    stop_reader: threading.Event


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
                shell=os.name == "nt",
            )
    else:
        result = subprocess.run(
            resolved,
            cwd=str(cwd) if cwd else None,
            text=True,
            shell=os.name == "nt",
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


def compute_file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_npm_state_hash(project_dir: Path) -> str:
    package_json = project_dir / "package.json"
    package_lock = project_dir / "package-lock.json"
    digest_source = [f"package.json:{compute_file_sha256(package_json)}"]
    if package_lock.exists():
        digest_source.append(f"package-lock.json:{compute_file_sha256(package_lock)}")
    else:
        digest_source.append("package-lock.json:missing")
    return hashlib.sha256("|".join(digest_source).encode("utf-8")).hexdigest()


def npm_state_stamp_path(project_dir: Path) -> Path:
    return project_dir / "node_modules" / ".bootstrap-npm-state"


def read_npm_state_stamp(project_dir: Path) -> str | None:
    stamp_path = npm_state_stamp_path(project_dir)
    if not stamp_path.exists():
        return None
    return stamp_path.read_text(encoding="utf-8").strip() or None


def write_npm_state_stamp(project_dir: Path, state_hash: str) -> None:
    stamp_path = npm_state_stamp_path(project_dir)
    stamp_path.parent.mkdir(parents=True, exist_ok=True)
    stamp_path.write_text(state_hash + "\n", encoding="utf-8")


def ensure_npm_project(project_dir: Path, label: str, log_name: str) -> None:
    package_json = project_dir / "package.json"
    if not package_json.exists():
        raise BootstrapError(f"{label}: package.json 누락 ({project_dir})")

    should_install = True
    desired_state_hash = compute_npm_state_hash(project_dir)
    node_modules_dir = project_dir / "node_modules"
    if node_modules_dir.exists():
        saved_state_hash = read_npm_state_stamp(project_dir)
        if saved_state_hash == desired_state_hash:
            info(f"{label}: node_modules 상태 일치 (npm install 생략)")
            should_install = False
        else:
            info(f"{label}: 의존성 상태 변경 감지 (npm install 실행)")

    if not should_install:
        return

    info(f"{label}: npm install 실행")
    run_command(["npm", "install"], cwd=project_dir, log_file=LOG_DIR / log_name)
    write_npm_state_stamp(project_dir, compute_npm_state_hash(project_dir))


def parse_args() -> BootstrapOptions:
    parser = argparse.ArgumentParser(description="FarmOS 통합 부트스트랩")
    parser.add_argument(
        "--verbose-table-info",
        action="store_true",
        help="DB 초기화 요약에 테이블 상세(컬럼/row 수)를 출력",
    )
    args = parser.parse_args()
    return BootstrapOptions(verbose_table_info=args.verbose_table_info)


def ensure_databases(options: BootstrapOptions) -> None:
    """DB/테이블 점검 및 필요 시 초기화를 `bootstrap/` 하위에 위임한다."""
    info("ShoppingMall DB 점검/초기화")
    shop_command = [
        "python",
        str(Path("bootstrap") / "shoppingmall.py"),
        "--mode",
        "ensure",
        "--skip-sync",
    ]
    if options.verbose_table_info:
        shop_command.append("--verbose-table-info")
    run_command(shop_command, cwd=ROOT)
    info("FarmOS DB 점검/초기화")
    farmos_command = [
        "python",
        str(Path("bootstrap") / "farmos.py"),
        "--mode",
        "ensure",
        "--skip-sync",
    ]
    if options.verbose_table_info:
        farmos_command.append("--verbose-table-info")
    run_command(farmos_command, cwd=ROOT)


def start_service(
    name: str,
    command: Iterable[str],
    cwd: Path,
    log_name: str,
) -> ServiceProcess:
    log_path = LOG_DIR / log_name
    log_handle = log_path.open("w", encoding="utf-8")
    creationflags = 0
    if os.name == "nt":
        # 자식 프로세스의 콘솔 제어 이벤트가 부모 부트스트랩까지 전파되지 않도록 분리한다.
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    proc = subprocess.Popen(
        resolve_command(list(command)),
        cwd=str(cwd),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
        shell=os.name == "nt",
    )
    info(f"시작됨: {name} (PID={proc.pid})")
    return ServiceProcess(
        name=name, process=proc, log_handle=log_handle, log_path=log_path
    )


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
        if (
            len(parts) >= 5
            and parts[1].rsplit(":", 1)[-1] == str(port)
            and parts[-1].isdigit()
        ):
            pids.add(int(parts[-1]))
    return sorted(pids)


def read_log_tail(path: Path, line_count: int = 30) -> list[str]:
    if line_count <= 0 or not path.exists():
        return []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        lines = handle.read().splitlines()
    return lines[-line_count:]


def report_service_failures(services: list[ServiceProcess]) -> tuple[bool, bool]:
    has_failure = False
    any_running = False
    for service in services:
        return_code = service.process.poll()
        if return_code is None:
            any_running = True
            continue
        if service.exit_reported:
            continue
        service.exit_code = return_code
        service.exit_reported = True
        if return_code == 0:
            info(f"종료됨: {service.name} (PID={service.process.pid}, code=0)")
            continue
        has_failure = True
        info(
            f"오류: {service.name} 비정상 종료 (PID={service.process.pid}, code={return_code})"
        )
        tail_lines = read_log_tail(service.log_path, line_count=30)
        if tail_lines:
            print(f"[Bootstrap] {service.name} 최근 로그 (마지막 30줄):")
            for line in tail_lines:
                print(f"[Bootstrap]   {line}")
        else:
            print(
                f"[Bootstrap] {service.name} 로그가 비어 있거나 읽을 수 없습니다: {service.log_path}"
            )
    all_stopped = bool(services) and not any_running
    return has_failure, all_stopped


def start_input_reader(command_queue: queue.Queue[str | None]) -> InputReaderController:
    prompt_request = threading.Event()
    stop_reader = threading.Event()

    def reader() -> None:
        while not stop_reader.is_set():
            if not prompt_request.wait(timeout=0.2):
                continue
            prompt_request.clear()
            if stop_reader.is_set():
                break
            try:
                user_input = input("> ")
            except EOFError:
                command_queue.put(None)
                continue
            if stop_reader.is_set():
                break
            command_queue.put(user_input)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    return InputReaderController(
        thread=thread, prompt_request=prompt_request, stop_reader=stop_reader
    )


def stop_services(services: list[ServiceProcess]) -> None:
    info("서비스 종료 중...")
    for service in services:
        if service.process.poll() is None:
            info(f"종료: {service.name} (PID={service.process.pid})")
            stop_process_tree(service.process.pid)
        service.log_handle.close()
    for port in PORTS:
        for pid in pids_from_port(port):
            stop_process_tree(pid)


def run(options: BootstrapOptions) -> None:
    os.chdir(ROOT)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    info("FarmOS 통합 부트스트랩 시작")
    info("FarmOS Backend   : http://localhost:8000")
    info("FarmOS Frontend  : http://localhost:5173")
    info("Shop Backend     : http://localhost:4000")
    info("Shop Frontend    : http://localhost:5174")

    check_required_tools()
    ensure_databases(options)

    ensure_uv_project(FARMOS_BACKEND_DIR, "FarmOS Backend", "farmos-be-setup.log")
    ensure_uv_project(SHOP_BACKEND_DIR, "Shop Backend", "shop-be-setup.log")
    ensure_npm_project(FARMOS_FRONTEND_DIR, "FarmOS Frontend", "farmos-fe-install.log")
    ensure_npm_project(SHOP_FRONTEND_DIR, "Shop Frontend", "shop-fe-install.log")

    services: list[ServiceProcess] = []
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
        command_queue: queue.Queue[str | None] = queue.Queue()
        input_controller = start_input_reader(command_queue)
        input_controller.prompt_request.set()
        input_closed = False
        while True:
            has_failure, all_stopped = report_service_failures(services)
            if has_failure:
                info("하위 서비스 오류로 인해 종료 절차를 시작합니다.")
                input_controller.stop_reader.set()
                break
            if all_stopped:
                info("모든 하위 서비스가 종료되어 종료 절차를 시작합니다.")
                input_controller.stop_reader.set()
                break
            try:
                user_input = command_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if user_input is None:
                if not input_closed:
                    info("표준 입력을 읽을 수 없어 입력 종료 기능을 비활성화합니다.")
                    info("종료하려면 Ctrl+C 를 누르세요.")
                    input_closed = True
                input_controller.stop_reader.set()
                continue
            command = user_input.strip().lower()
            if command in {"x", "q", "exit", "quit"}:
                input_controller.stop_reader.set()
                break
            if command == "":
                print("종료하려면 x/q/exit 를 입력하세요.")
            if not input_closed:
                input_controller.prompt_request.set()
    finally:
        stop_services(services)
        print("모든 서비스를 종료했습니다.")


if __name__ == "__main__":
    try:
        run(parse_args())
    except KeyboardInterrupt:
        print("\n사용자 인터럽트로 종료합니다.")
        raise SystemExit(130) from None
    except BootstrapError as exc:
        fail(str(exc))
