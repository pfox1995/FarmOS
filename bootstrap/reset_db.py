import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))
load_dotenv(dotenv_path=backend_dir / ".env")

from app.core.database import engine
from sqlalchemy import text

def _is_local_database(db_url: str) -> bool:
    parsed = urlparse(db_url)
    host = (parsed.hostname or "").lower()
    return host in {"localhost", "127.0.0.1"}


def _confirm_reset() -> None:
    db_url = os.getenv("DATABASE_URL", "")
    parsed = urlparse(db_url)
    db_name = (parsed.path or "").lstrip("/") or "unknown"

    print("WARNING: This will delete ALL data in the database.")
    print(f"Target DB: {db_name}")

    if not _is_local_database(db_url):
        print("WARNING: DATABASE_URL host is not localhost/127.0.0.1")
        check_name = input(f"Type target database name '{db_name}' to continue: ")
        if check_name != db_name:
            print("Aborted.")
            raise SystemExit(1)

    confirm = input("Are you sure? Type 'YES' to continue: ")
    if confirm != "YES":
        print("Aborted.")
        raise SystemExit(1)


async def drop_all() -> None:
    try:
        async with engine.begin() as conn:
            print("Dropping public schema cascade...")
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            print("Recreating public schema...")
            await conn.execute(text("CREATE SCHEMA public"))
            print("Granting privileges on public schema...")
            await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
        
        print("\nDatabase has been completely wiped!")
        print("You can now run 'bootstrap.cmd' to recreate tables and reseed data.")
    except Exception as e:
        print(f"Error dropping database: {e}")
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    _confirm_reset()
    asyncio.run(drop_all())
