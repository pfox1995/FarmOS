#!/usr/bin/env python
"""FarmOS 백엔드 실행 스크립트.

주의:
- DB 검증/초기화는 bootstrap/farmos_seed.py가 담당한다.
- 이 파일은 서버 실행(uv run main.py)만 담당한다.
"""

from __future__ import annotations

import argparse

from _bootstrap_common import (  # type: ignore[import-not-found]
    BACKEND_DIR,
    BootstrapError,
    error,
    info,
    run_command,
    set_log_prefix,
)

LOG_PREFIX = "FarmOS"


def main() -> int:
    parser = argparse.ArgumentParser(description="FarmOS 백엔드 실행")
    parser.add_argument(
        "--skip-sync",
        action="store_true",
        help="uv sync를 생략하고 서버만 실행합니다.",
    )
    args = parser.parse_args()

    try:
        set_log_prefix(LOG_PREFIX)
        if not args.skip_sync:
            info("FarmOS backend 의존성 동기화(uv sync) - 시간이 많이 걸릴 수 있습니다")
            run_command(["uv", "sync"], cwd=BACKEND_DIR)
        info("FarmOS 백엔드 서버 시작")
        run_command(["uv", "run", "main.py"], cwd=BACKEND_DIR)
        return 0
    except BootstrapError as exc:
        error(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
