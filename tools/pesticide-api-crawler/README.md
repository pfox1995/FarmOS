# API Crawler (FarmOS)

식품안전나라 `I1910` 데이터를 수집(`crawler.py`)하는 도구입니다.  
전처리/ PostgreSQL 적재는 이제 `bootstrap/pesticide.py`가 담당합니다.

## 구성 파일

- `crawler.py`: API 원본 JSON 수집(`json_raw/`) + 선택적으로 SQLite `rag_pesticide_rows` 적재
- `.env.example`: crawler/적재 공용 PostgreSQL 기본 접속값 샘플
- `pyproject.toml`: 실행 의존성 정의

## 사전 준비 (uv)

```powershell
cd path/to/FarmOS/tools/api-crawler
uv sync
```

기본 env 파일 경로:
- `path/to/FarmOS/backend/.env` (`crawler.py` API 키)
- `path/to/FarmOS/tools/api-crawler/.env.example` (적재용 PostgreSQL 기본 fallback 값 샘플)

주요 환경 변수:
- `FOOD_SAFETY_API_KEY` (`crawler.py`에서 사용, 기본 env 이름)
- `DATABASE_URL`
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`

## 빠른 실행

```powershell
cd path/to/FarmOS/tools/api-crawler

# 1) API 1배치 수집 (json_raw + sqlite3/data.sqlite3 + progress.json)
uv run crawler.py --max-batches 1 --delay-seconds 0

# 2) FarmOS bootstrap로 PostgreSQL RAG 테이블 적재
cd path/to/FarmOS/backend
uv run python ..\bootstrap\pesticide.py --db-type postgresql --input-dir ..\tools\api-crawler\json_raw
```

## 중복/재적재 정책

- `bootstrap/pesticide.py` 기본 모드(`--append` 미사용): 관리 테이블을 `drop/create` 후 전체 적재
- `bootstrap/pesticide.py --append`: 기존 테이블 유지 + upsert 누적 적재
  - `rag_pesticide_products`: `product_id` 기준 upsert
  - `rag_pesticide_crops`: `crop_name_normalized` 기준 재사용
  - `rag_pesticide_targets`: `(target_name_normalized, target_kind)` 기준 재사용
  - `rag_pesticide_product_applications`: `(product_id, crop_id, target_id)` 기준 upsert
  - `rag_pesticide_documents`: `application_id` 기준 upsert

`crawler.py`는 범위 기반 id(`start_idx + row_index + 1`)로 `rag_pesticide_rows`를 upsert하며,
동일 범위를 다시 수집하면 해당 id 구간을 갱신합니다.

## PRDLST_KOR_NM 명칭 처리

원본 API의 `PRDLST_KOR_NM`은 의미상 성분/제형 정보에 가까워,
전처리 결과에서는 `ingredient_or_formulation_name` 컬럼으로 저장합니다.

## CLI 옵션

### crawler.py

- `--env-name`: API 키 환경변수명 (기본 `FOOD_SAFETY_API_KEY`)
- `--env-path`: API 키를 읽을 env 파일 경로 (기본 `backend/.env`)
- `--start-idx`: 초기 시작 인덱스 (기본 `0`, `state-path`가 있으면 state 우선)
- `--batch-size`: 요청 row 수 (기본 `1000`, 최대 `1000`)
- `--delay-seconds`: 요청 간 대기 시간(초, 기본 `60`)
- `--timeout-seconds`: HTTP 타임아웃(초, 기본 `30`)
- `--api-max-retries`: API 재시도 횟수 (기본 `10`)
- `--change-date YYYYMMDD`: 변경일자 이후 데이터만 수집
- `--state-path`: 진행 상태 파일 경로 (기본 `progress.json`)
- `--raw-dir` / `--result-dir`: raw JSON 출력 디렉터리 (기본 `json_raw`)
- `--db-path`: SQLite 파일 경로 (기본 `sqlite3/data.sqlite3`)
- `--max-batches`: 이번 실행에서 처리할 최대 배치 수 (`0`이면 무제한)
- `--disable-db`: SQLite 저장 비활성화
- `--rebuild-db-from-json`: `json_raw/*.json`로 SQLite 재생성

### bootstrap/pesticide.py

- `--input-dir`: raw JSON 입력 디렉터리 (기본 `json_raw`)
- `--glob`: 입력 파일 패턴 (기본 `*.json`)
- `--backend-env-path`: backend env 파일 경로 (기본 `backend/.env`)
- `--db-type`: `sqlite` 또는 `postgresql` (기본 `sqlite`)
- `--sqlite-path`: SQLite 파일 경로 (기본 `sqlite3/rag.sqlite3`)
- `--db-url`: DB URL 직접 지정 (개별 DB 옵션보다 우선)
- `--postgres-host`, `--postgres-port`, `--postgres-user`, `--postgres-password`, `--postgres-db`: PostgreSQL 접속 정보 오버라이드
- `--append`: 테이블 유지 + upsert 누적 적재
- `--log-every`: 중간 로그 주기(처리 row 수 기준, 기본 `5000`)
- `--postgres-max-retries`: PostgreSQL 연결 재시도 횟수 (기본 `10`)
