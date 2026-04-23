from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from sqlalchemy import Integer, String, Text, create_engine, inspect
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

API_BASE_URL = "http://openapi.foodsafetykorea.go.kr/api"
SERVICE_ID = "I1910"
DATA_TYPE = "json"
DEFAULT_BATCH_SIZE = 1000
DEFAULT_DELAY_SECONDS = 60.0
DEFAULT_STATE_PATH = Path("progress.json")
DEFAULT_RAW_DIR = Path("json_raw")
DEFAULT_DB_PATH = Path("sqlite3/data.sqlite3")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BACKEND_ENV_PATH = PROJECT_ROOT / "backend" / ".env"
API_RETRY_INTERVAL_SECONDS = 5.0
SUCCESS_CODE = "INFO-000"
RESULT_FILE_PATTERN = re.compile(r"^(?P<start>\d+)-(?P<end>\d+)\.json$")
MESSAGE_CODE_DESCRIPTIONS = {
    "ERROR-300": "필수 값이 누락되어 있습니다. 요청인자를 참고하십시오.",
    "ERROR-301": "파일타입 값이 누락 혹은 유효하지 않습니다.",
    "ERROR-310": "해당하는 서비스를 찾을 수 없습니다.",
    "ERROR-331": "요청시작위치 값을 확인하십시오.",
    "ERROR-332": "요청종료위치 값을 확인하십시오.",
    "ERROR-334": "종료위치보다 시작위치가 더 큽니다.",
    "ERROR-336": "데이터요청은 한번에 최대 1000건을 넘을 수 없습니다.",
    "ERROR-500": "서버오류입니다.",
    "ERROR-601": "SQL 문장 오류입니다.",
    "INFO-000": "정상 처리되었습니다.",
    "INFO-100": "인증키가 유효하지 않습니다.",
    "INFO-200": "해당하는 데이터가 없습니다.",
    "INFO-300": "유효 호출건수를 이미 초과하셨습니다.",
    "INFO-400": "권한이 없습니다. 관리자에게 문의하십시오.",
}
ROW_FIELD_NAMES = [
    "ADDR",  # 주소
    "AGCHM_DVS_NM",  # 농약구분
    "AGCHM_PRDLST_NO",  # 품목번호
    "AGCHM_USE_MTHD",  # 농약사용방법
    "BRND_NM",  # 상표명
    "BUSS_REG_EVNT_NM",  # 업등록종목
    "BUSS_REG_NO",  # 업등록종목
    "CPR_NM",  # 법인명
    "CROPS_NM",  # 작물명
    "DILU_DRNG",  # 희석배수
    "ECLGY_TOXCTY",  # 생태독성
    "MDC_SHAP_NM",  # 제제형태
    "MNF_INCM_DVS_NM",  # 제조/수입구분
    "PERSN_LVSTCK_TOXCTY",  # 사람/가축독성
    "PRDLST_ENG_NM",  # 농약영문명
    "PRDLST_KOR_NM",  # 농약명
    "PRDLST_REG_DT",  # 등록일자
    "PRDLST_REG_NO",  # 등록번호
    "PRDLST_REG_STND",  # 등록규격
    "PRDLST_REG_VALD_DT",  # 등록유효일자
    "PRPOS_DVS_CD_NM",  # 용도
    "PRSDNT_NM",  # 대표자
    "REG_YN_NM",  # 등록여부
    "SICKNS_HLSCT_NM_WEEDS_NM",  # 병해충/잡초명
    "TEST_DRGS_NM",  # 시험약제명
    "USE_PPRTM",  # 사용적기
    "USE_QTY",  # 사용수량
    "USE_TMNO",  # 사용횟수
    "USE_UNIT",  # 단위
]

PARSER = argparse.ArgumentParser(
    description="식품의약품안전처 I1910 농약등록정보를 배치 단위로 수집합니다."
)
PARSER.add_argument(
    "--env-name",
    default="FOOD_SAFETY_API_KEY",
    help="API 키를 읽을 환경 변수 이름",
)
PARSER.add_argument(
    "--env-path",
    type=Path,
    default=DEFAULT_BACKEND_ENV_PATH,
    help="API 키를 읽을 backend/.env 파일 경로",
)
PARSER.add_argument(
    "--start-idx",
    type=int,
    default=0,
    help="초기 시작 인덱스. 상태 파일이 있으면 무시됩니다.",
)
PARSER.add_argument(
    "--batch-size",
    type=int,
    default=DEFAULT_BATCH_SIZE,
    help="한 번에 조회할 row 수",
)
PARSER.add_argument(
    "--delay-seconds",
    type=float,
    default=DEFAULT_DELAY_SECONDS,
    help="성공한 요청 사이 대기 시간(초)",
)
PARSER.add_argument(
    "--timeout-seconds",
    type=float,
    default=30.0,
    help="HTTP 요청 타임아웃(초)",
)
PARSER.add_argument(
    "--api-max-retries",
    type=int,
    default=10,
    help="API 요청 재시도 최대 횟수(기본 10회)",
)
PARSER.add_argument(
    "--change-date",
    help="변경일자 기준 이후 자료만 조회합니다. 형식: YYYYMMDD",
)
PARSER.add_argument(
    "--state-path",
    type=Path,
    default=DEFAULT_STATE_PATH,
    help="진행 상태 JSON 파일 경로",
)
PARSER.add_argument(
    "--raw-dir",
    "--result-dir",
    dest="raw_dir",
    type=Path,
    default=DEFAULT_RAW_DIR,
    help="API 원본 JSON 저장 디렉터리",
)
PARSER.add_argument(
    "--db-path",
    type=Path,
    default=DEFAULT_DB_PATH,
    help="SQLite DB 저장 경로",
)
PARSER.add_argument(
    "--max-batches",
    type=int,
    default=0,
    help="이번 실행에서 처리할 최대 배치 수. 0이면 제한 없음",
)
PARSER.add_argument(
    "--disable-db",
    action="store_true",
    help="SQLite 저장을 비활성화합니다.",
)
PARSER.add_argument(
    "--rebuild-db-from-json",
    action="store_true",
    help="기존 DB를 삭제하고 json_raw/*.json 파일을 읽어 SQLite DB를 다시 생성합니다.",
)


class Base(DeclarativeBase):
    pass


class PesticideRow(Base):
    __tablename__ = "pesticide_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reg_yn_nm: Mapped[str | None] = mapped_column("REG_YN_NM", Text, nullable=True)
    prsdnt_nm: Mapped[str | None] = mapped_column("PRSDNT_NM", Text, nullable=True)
    agchm_use_mthd: Mapped[str | None] = mapped_column(
        "AGCHM_USE_MTHD", Text, nullable=True
    )
    use_pprtm: Mapped[str | None] = mapped_column("USE_PPRTM", Text, nullable=True)
    prdlst_reg_no: Mapped[str | None] = mapped_column(
        "PRDLST_REG_NO", Text, nullable=True
    )
    prdlst_reg_dt: Mapped[str | None] = mapped_column(
        "PRDLST_REG_DT", Text, nullable=True
    )
    test_drgs_nm: Mapped[str | None] = mapped_column(
        "TEST_DRGS_NM", Text, nullable=True
    )
    prdlst_reg_vald_dt: Mapped[str | None] = mapped_column(
        "PRDLST_REG_VALD_DT", Text, nullable=True
    )
    prdlst_reg_stnd: Mapped[str | None] = mapped_column(
        "PRDLST_REG_STND", Text, nullable=True
    )
    use_unit: Mapped[str | None] = mapped_column("USE_UNIT", Text, nullable=True)
    mnf_incm_dvs_nm: Mapped[str | None] = mapped_column(
        "MNF_INCM_DVS_NM", Text, nullable=True
    )
    persn_lvstck_toxcty: Mapped[str | None] = mapped_column(
        "PERSN_LVSTCK_TOXCTY", Text, nullable=True
    )
    use_tmno: Mapped[str | None] = mapped_column("USE_TMNO", Text, nullable=True)
    cpr_nm: Mapped[str | None] = mapped_column("CPR_NM", Text, nullable=True)
    prdlst_kor_nm: Mapped[str | None] = mapped_column(
        "PRDLST_KOR_NM", Text, nullable=True
    )
    prdlst_eng_nm: Mapped[str | None] = mapped_column(
        "PRDLST_ENG_NM", Text, nullable=True
    )
    agchm_prdlst_no: Mapped[str | None] = mapped_column(
        "AGCHM_PRDLST_NO", Text, nullable=True
    )
    mdc_shap_nm: Mapped[str | None] = mapped_column("MDC_SHAP_NM", Text, nullable=True)
    sickns_hlsct_nm_weeds_nm: Mapped[str | None] = mapped_column(
        "SICKNS_HLSCT_NM_WEEDS_NM", Text, nullable=True
    )
    brnd_nm: Mapped[str | None] = mapped_column("BRND_NM", Text, nullable=True)
    agchm_dvs_nm: Mapped[str | None] = mapped_column(
        "AGCHM_DVS_NM", Text, nullable=True
    )
    buss_reg_no: Mapped[str | None] = mapped_column("BUSS_REG_NO", Text, nullable=True)
    buss_reg_evnt_nm: Mapped[str | None] = mapped_column(
        "BUSS_REG_EVNT_NM", Text, nullable=True
    )
    addr: Mapped[str | None] = mapped_column("ADDR", Text, nullable=True)
    crops_nm: Mapped[str | None] = mapped_column("CROPS_NM", Text, nullable=True)
    use_qty: Mapped[str | None] = mapped_column("USE_QTY", Text, nullable=True)
    prpos_dvs_cd_nm: Mapped[str | None] = mapped_column(
        "PRPOS_DVS_CD_NM", Text, nullable=True
    )
    dilu_drng: Mapped[str | None] = mapped_column("DILU_DRNG", Text, nullable=True)
    eclgy_toxcty: Mapped[str | None] = mapped_column(
        "ECLGY_TOXCTY", Text, nullable=True
    )
    extra_fields_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    inserted_at: Mapped[str] = mapped_column(String, nullable=False)


@dataclass
class CrawlRange:
    start_idx: int
    end_idx: int

    @property
    def filename(self) -> str:
        return f"{self.start_idx:05d}-{self.end_idx:05d}.json"

    def next_range(self, batch_size: int) -> "CrawlRange":
        start = self.end_idx + 1
        end = start + batch_size - 1
        return CrawlRange(start_idx=start, end_idx=end)


def parse_args() -> argparse.Namespace:
    return PARSER.parse_args()


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(message: str) -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_api_key(env_name: str, env_path: Path) -> str:
    load_dotenv(dotenv_path=env_path, override=False)
    api_key = os.getenv(env_name, "").strip()
    if not api_key:
        raise RuntimeError(
            f"환경 변수 `{env_name}` 가 비어 있습니다. `{env_path.as_posix()}` 파일에 API 키를 설정하세요."
        )
    return api_key


def load_state(state_path: Path, batch_size: int, start_idx: int) -> CrawlRange:
    if state_path.exists():
        with state_path.open("r", encoding="utf-8") as fp:
            raw = json.load(fp)
        return CrawlRange(start_idx=int(raw["startIdx"]), end_idx=int(raw["endIdx"]))

    end_idx = start_idx + batch_size - 1
    return CrawlRange(start_idx=start_idx, end_idx=end_idx)


def save_state(state_path: Path, crawl_range: CrawlRange) -> None:
    ensure_parent_dir(state_path)
    with state_path.open("w", encoding="utf-8") as fp:
        json.dump(
            {
                "startIdx": crawl_range.start_idx,
                "endIdx": crawl_range.end_idx,
                "updatedAt": utcnow_iso(),
            },
            fp,
            ensure_ascii=False,
            indent=2,
        )


def build_url(api_key: str, crawl_range: CrawlRange) -> str:
    return (
        f"{API_BASE_URL}/{api_key}/{SERVICE_ID}/{DATA_TYPE}/"
        f"{crawl_range.start_idx}/{crawl_range.end_idx}"
    )


def build_optional_path_segments(change_date: str | None) -> list[str]:
    return [f"CHNG_DT={change_date}"] if change_date else []


def fetch_batch(
    session: requests.Session,
    api_key: str,
    crawl_range: CrawlRange,
    timeout_seconds: float,
    change_date: str | None,
) -> dict[str, Any]:
    url = build_url(api_key, crawl_range)
    extra_segments = build_optional_path_segments(change_date)
    if extra_segments:
        url = f"{url}/{'&'.join(extra_segments)}"

    response = session.get(url, timeout=timeout_seconds)
    response.raise_for_status()

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(
            "JSON 파싱 실패: "
            f"status={response.status_code}, "
            f"content_type={response.headers.get('Content-Type', '')!r}, "
            f"url={url}, "
            f"body_preview={response.text[:500].strip()!r}"
        ) from exc


def fetch_batch_with_retry(
    session: requests.Session,
    api_key: str,
    crawl_range: CrawlRange,
    timeout_seconds: float,
    change_date: str | None,
    max_retries: int,
) -> dict[str, Any] | None:
    attempt = 0
    while attempt < max_retries:
        attempt += 1
        try:
            return fetch_batch(
                session=session,
                api_key=api_key,
                crawl_range=crawl_range,
                timeout_seconds=timeout_seconds,
                change_date=change_date,
            )
        except (requests.RequestException, RuntimeError) as exc:
            if attempt >= max_retries:
                log(
                    "API 요청 재시도 초과: "
                    f"range={crawl_range.start_idx}-{crawl_range.end_idx}, "
                    f"attempts={max_retries}, last_error={exc}"
                )
                return None
            log(
                "API 요청 실패: "
                f"attempt={attempt}/{max_retries}, {exc}. "
                f"{int(API_RETRY_INTERVAL_SECONDS)}초 후 재시도합니다."
            )
            time.sleep(API_RETRY_INTERVAL_SECONDS)
    return None


def extract_dataset(payload: dict[str, Any]) -> dict[str, Any]:
    dataset = payload.get(SERVICE_ID)
    if not isinstance(dataset, dict):
        raise RuntimeError(f"응답에 `{SERVICE_ID}` 객체가 없습니다.")
    return dataset


def extract_result(dataset: dict[str, Any]) -> tuple[str, str]:
    result = dataset.get("RESULT")
    if not isinstance(result, dict):
        raise RuntimeError("응답에 `RESULT` 객체가 없습니다.")
    return str(result.get("CODE", "")).strip(), str(result.get("MSG", "")).strip()


def describe_message_code(code: str, message: str) -> str:
    description = MESSAGE_CODE_DESCRIPTIONS.get(code, "")
    if message and description and message != description:
        return f"{message} / {description}"
    if message:
        return message
    if description:
        return description
    return "알 수 없는 응답 코드입니다."


def extract_rows(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    rows = dataset.get("row", [])
    if rows is None:
        return []
    if not isinstance(rows, list):
        raise RuntimeError("응답의 `row` 가 배열이 아닙니다.")
    return [row if isinstance(row, dict) else {"_raw": row} for row in rows]


def stringify_row_value(value: Any) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) else str(value)


def build_pesticide_row_values(
    row: dict[str, Any],
    *,
    record_id: int,
    inserted_at: str,
) -> dict[str, Any]:
    known_values = {
        field_name: stringify_row_value(row.get(field_name))
        for field_name in ROW_FIELD_NAMES
    }
    extra_fields = {
        key: value for key, value in row.items() if key not in ROW_FIELD_NAMES
    }
    return {
        "id": record_id,
        **known_values,
        "extra_fields_json": json.dumps(
            extra_fields, ensure_ascii=False, sort_keys=True
        )
        if extra_fields
        else None,
        "inserted_at": inserted_at,
    }


def write_json(raw_dir: Path, crawl_range: CrawlRange, payload: dict[str, Any]) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    output_path = raw_dir / crawl_range.filename
    with output_path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)
    return output_path


def drop_legacy_tables(engine: Any) -> None:
    existing_tables = inspect(engine).get_table_names()
    legacy_tables = sorted(
        table_name for table_name in existing_tables if table_name != "pesticide_rows"
    )
    if not legacy_tables:
        return

    with engine.begin() as conn:
        for table_name in legacy_tables:
            conn.exec_driver_sql(f'DROP TABLE IF EXISTS "{table_name}"')


def open_db(db_path: Path):
    ensure_parent_dir(db_path)
    engine = create_engine(f"sqlite:///{db_path.as_posix()}", future=True)
    drop_legacy_tables(engine)
    Base.metadata.create_all(engine)
    return engine


def insert_batch_into_db(
    session: Session, crawl_range: CrawlRange, dataset: dict[str, Any]
) -> None:
    rows = extract_rows(dataset)
    now = utcnow_iso()
    start_record_id = crawl_range.start_idx + 1
    end_record_id = crawl_range.start_idx + len(rows)

    if rows:
        session.query(PesticideRow).filter(
            PesticideRow.id >= start_record_id,
            PesticideRow.id <= end_record_id,
        ).delete()

    for row_number, row in enumerate(rows, start=1):
        row_values = build_pesticide_row_values(
            row,
            record_id=crawl_range.start_idx + row_number,
            inserted_at=now,
        )
        row_stmt = sqlite_insert(PesticideRow).values(row_values)
        session.execute(
            row_stmt.on_conflict_do_update(
                index_elements=[PesticideRow.id],
                set_={
                    column.name: getattr(row_stmt.excluded, column.name)
                    for column in PesticideRow.__table__.columns
                    if column.name != "id"
                },
            )
        )

    session.commit()


def reset_db_files(db_path: Path) -> None:
    for path in (
        db_path,
        db_path.with_suffix(db_path.suffix + "-wal"),
        db_path.with_suffix(db_path.suffix + "-shm"),
    ):
        if path.exists():
            path.unlink()


def parse_range_from_result_path(path: Path) -> CrawlRange:
    match = RESULT_FILE_PATTERN.match(path.name)
    if not match:
        raise RuntimeError(
            f"파일명 `{path.name}` 이 `00000-00999.json` 형식이 아닙니다."
        )
    return CrawlRange(
        start_idx=int(match.group("start")), end_idx=int(match.group("end"))
    )


def load_payload_from_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)
    if not isinstance(payload, dict):
        raise RuntimeError(
            f"`{path.as_posix()}` 의 JSON 최상위 구조가 객체가 아닙니다."
        )
    return payload


def rebuild_db_from_json_files(raw_dir: Path, db_path: Path) -> int:
    json_files = sorted(raw_dir.glob("*.json"))
    if not json_files:
        raise RuntimeError(f"`{raw_dir.as_posix()}` 에 재적재할 JSON 파일이 없습니다.")

    ensure_parent_dir(db_path)
    reset_db_files(db_path)
    engine = open_db(db_path)
    with Session(engine) as db_session:
        for json_file in json_files:
            dataset = extract_dataset(load_payload_from_file(json_file))
            status_code, status_message = extract_result(dataset)
            if status_code != SUCCESS_CODE:
                raise RuntimeError(
                    f"`{json_file.as_posix()}` 의 RESULT.CODE={status_code}, MSG={status_message}"
                )
            insert_batch_into_db(
                db_session, parse_range_from_result_path(json_file), dataset
            )
            log(f"DB 재적재 완료: {json_file.as_posix()}")

    return 0


def run() -> int:
    args = parse_args()

    if args.batch_size <= 0:
        raise RuntimeError("--batch-size 는 1 이상이어야 합니다.")
    if args.batch_size > DEFAULT_BATCH_SIZE:
        raise RuntimeError("--batch-size 는 1000을 넘을 수 없습니다.")
    if args.change_date and not re.fullmatch(r"\d{8}", args.change_date):
        raise RuntimeError("--change-date 는 YYYYMMDD 형식의 8자리 숫자여야 합니다.")
    if args.api_max_retries <= 0:
        raise RuntimeError("--api-max-retries 는 1 이상이어야 합니다.")

    if args.rebuild_db_from_json:
        if args.disable_db:
            raise RuntimeError(
                "--rebuild-db-from-json 과 --disable-db 는 함께 사용할 수 없습니다."
            )
        return rebuild_db_from_json_files(args.raw_dir, args.db_path)

    api_key = load_api_key(args.env_name, args.env_path)
    crawl_range = load_state(args.state_path, args.batch_size, args.start_idx)
    http_session = requests.Session()
    http_session.headers.update({"User-Agent": "api-crawler/1.0"})
    engine = None if args.disable_db else open_db(args.db_path)
    processed_batches = 0

    try:
        db_context = Session(engine) if engine is not None else nullcontext(None)
        with db_context as db_session:
            while True:
                save_state(args.state_path, crawl_range)
                log(
                    f"현재 작업 지점 저장: startIdx={crawl_range.start_idx}, endIdx={crawl_range.end_idx}"
                )
                log(f"요청 시작: {crawl_range.start_idx} ~ {crawl_range.end_idx}")

                payload = fetch_batch_with_retry(
                    session=http_session,
                    api_key=api_key,
                    crawl_range=crawl_range,
                    timeout_seconds=args.timeout_seconds,
                    change_date=args.change_date,
                    max_retries=args.api_max_retries,
                )
                if payload is None:
                    log("API 응답을 가져오지 못해 작업을 종료합니다.")
                    return 1
                dataset = extract_dataset(payload)
                status_code, status_message = extract_result(dataset)
                status_description = describe_message_code(status_code, status_message)

                if status_code == "INFO-200":
                    log(f"데이터 없음: {status_description}. 수집을 종료합니다.")
                    return 0
                if status_code == "INFO-300":
                    log(f"호출 한도 초과: {status_description}. 작업을 중단합니다.")
                    return 1
                if status_code != SUCCESS_CODE:
                    log(
                        f"경고: API RESULT.CODE={status_code}, MSG={status_description}. 작업을 중단합니다."
                    )
                    return 1

                file_path = write_json(args.raw_dir, crawl_range, payload)
                rows = extract_rows(dataset)
                log(
                    f"저장 완료: {file_path.as_posix()} ({len(rows)}건, total_count={dataset.get('total_count')})"
                )

                if db_session is not None:
                    insert_batch_into_db(db_session, crawl_range, dataset)
                    log(f"SQLite 저장 완료: {args.db_path.as_posix()}")

                if not rows:
                    log("응답 row 가 0건이므로 수집을 종료합니다.")
                    return 0

                processed_batches += 1
                next_range = crawl_range.next_range(args.batch_size)
                save_state(args.state_path, next_range)
                log(
                    f"다음 재시작 지점 저장: startIdx={next_range.start_idx}, endIdx={next_range.end_idx}"
                )

                if 0 < args.max_batches <= processed_batches:
                    log(
                        f"--max-batches={args.max_batches} 에 도달해 이번 실행을 종료합니다."
                    )
                    return 0

                if args.delay_seconds > 0:
                    log(f"{args.delay_seconds}초 대기 후 다음 요청을 진행합니다.")
                    time.sleep(args.delay_seconds)

                crawl_range = next_range
    finally:
        http_session.close()


if __name__ == "__main__":
    try:
        sys.exit(run())
    except KeyboardInterrupt:
        log("사용자 인터럽트로 종료합니다.")
        sys.exit(130)
    except Exception as exc:
        log(f"오류: {exc}")
        sys.exit(1)
