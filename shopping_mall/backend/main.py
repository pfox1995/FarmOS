import logging
import os
import sys

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import uvicorn  # noqa: E402 (환경변수 설정 후 import)

# stdout/stderr UTF-8 강제 (Windows cp949 방지)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(name)s: %(message)s",
    stream=sys.stdout,
    force=True,
)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=4000, reload=True, log_level="info")
