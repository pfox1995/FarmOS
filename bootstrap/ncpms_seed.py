import asyncio
import json
from pathlib import Path
from typing import Any

from _bootstrap_common import info
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

ROOT = Path(__file__).resolve().parent.parent
NCPMS_JSON_PATH = ROOT / "tools" / "ncpms-api-crawler" / "json_raw" / "ncpms_data.json"


def _load_json_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, dict)]


def _build_payload(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    payload: list[dict[str, str]] = []
    for row in items:
        pest = str(row.get("pest_name", "")).strip()
        crop = str(row.get("crop_name", "")).strip()
        if not pest or not crop:
            continue

        eco = str(row.get("ecologyInfo", "")).strip()
        bio = str(row.get("biologyPrvnbeMth", "")).strip()
        chem = str(row.get("chemicalPrvnbeMth", "")).strip()
        prev = str(row.get("preventMethod", "")).strip()

        payload.append(
            {
                "pest_name": pest,
                "crop_name": crop,
                "ecology_info": eco,
                "biology_prvnbe_mth": bio,
                "chemical_prvnbe_mth": chem,
                "prevent_method": prev,
                "formatted_markdown": (
                    f"### 생태 환경\n\n{eco}\n\n### 작물 보호 및 재배적 방제\n\n{prev}"
                ),
            }
        )
    return payload


async def run_ncpms_seed(_db_conf: dict[str, str]) -> None:
    # _db_conf 파라미터는 bootstrap.py (farmos_seed.py 등)와의 인터페이스 호환성을 위해 유지합니다.
    info("NCPMS 캐시 테이블 적재 스크립트 실행")
    if not NCPMS_JSON_PATH.exists():
        info(f"NCPMS 데이터 파일 없음: {NCPMS_JSON_PATH} (의도적 스킵 가능)")
        return

    try:
        items = await asyncio.to_thread(_load_json_rows, NCPMS_JSON_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        info(f"NCPMS 데이터 파일 읽기 실패: {exc}")
        return

    if not items:
        info("빈 JSON 파일 - 스킵")
        return

    payload = _build_payload(items)
    if not payload:
        info("유효한 NCPMS 데이터가 없어 적재를 스킵합니다.")
        return

    from app.core.database import async_session
    from app.models.ncpms import NcpmsDiagnosis

    async with async_session() as db:
        count_result = await db.execute(select(func.count()).select_from(NcpmsDiagnosis))
        current_count = int(count_result.scalar() or 0)
        info(f"NCPMS 적재 시작 (DB {current_count}건 -> JSON {len(payload)}건, UPSERT)")

        batch_size = 500
        for i in range(0, len(payload), batch_size):
            batch = payload[i : i + batch_size]
            stmt = pg_insert(NcpmsDiagnosis).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=["pest_name", "crop_name"],
                set_={
                    "ecology_info": stmt.excluded.ecology_info,
                    "biology_prvnbe_mth": stmt.excluded.biology_prvnbe_mth,
                    "chemical_prvnbe_mth": stmt.excluded.chemical_prvnbe_mth,
                    "prevent_method": stmt.excluded.prevent_method,
                    "formatted_markdown": stmt.excluded.formatted_markdown,
                },
            )
            await db.execute(stmt)

        await db.commit()

    info(f"NCPMS 데이터 적재 완료 (총 {len(payload)}건)")
