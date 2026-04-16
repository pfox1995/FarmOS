# Bootstrap 쉬운 안내서 (초심자용)

## 0. 이 문서 한 줄 요약

`bootstrap`은 개발 서버를 한 번에 켜주는 스크립트이고, DB 초기화는 필요할 때만 옵션으로 실행한다.

또한 팀 내 다른 요구를 반영해, Windows 래퍼는 '빠른 실행'과 'DB 확인 포함 실행'을 분리해 제공한다.

## 1. 제일 많이 쓰는 명령

### 1) 빠른 실행

- 더블클릭 파일: `bootstrap-fast.cmd`
- CLI 명령: `python bootstrap.py`
- 하는 일: 의존성 확인/설치 + 서버 실행
- 하지 않는 일: DB 점검/초기화

### 2) DB 확인 포함 실행

- 더블클릭 파일: `bootstrap.cmd`
- CLI 명령: `python bootstrap.py --initialize`
- 하는 일: DB 상태 확인(필요 시 재적재) + 의존성 확인/설치 + 서버 실행

### 3) 강제 스키마 재구성(주의)

- 실행 방법: `bootstrap.cmd`에 인자 전달

```bat
bootstrap.cmd --rebuild-schema
```

```bash
python bootstrap.py --initialize --rebuild-schema
```

- 하는 일: DB 초기화 과정에서 스키마 재구성까지 수행
- 주의: 파괴적 작업이므로 팀 합의 후 사용

### 4) 테이블 초기화 시 상세 정보까지 같이 보기

- 실행 방법: `bootstrap.cmd`에 인자 전달

```bat
bootstrap.cmd --verbose-table-info
```

```bash
python bootstrap.py --initialize --verbose-table-info
```

- 하는 일: 초기화 요약에 테이블 행 수/컬럼 정보 출력

래퍼가 둘로 나뉜 이유:

- 팀 내 요구가 충돌했기 때문
  - A: 기본 실행은 빠르고 안전해야 함 (DB 비개입)
  - B: 실행 시 DB 상태 확인이 필요함
- 그래서 사용자가 의도를 명확히 선택할 수 있게 2개 래퍼로 분리했다.
  - `bootstrap-fast.cmd`: 빠른 실행 전용
  - `bootstrap.cmd`: DB 확인 포함 실행

반영 요약:

- 실행 전 DB 상태 확인 필요성은 인정한다.
- 다만 이를 모든 실행의 기본값으로 강제하지 않고, 래퍼 선택으로 분리한다.
- DB 확인 흐름은 `bootstrap.cmd`, 빠른 개발 흐름은 `bootstrap-fast.cmd`로 제공한다.

## 2. 언제 어떤 명령을 써야 하나

- 그냥 개발 서버만 켜고 싶다
  - `bootstrap-fast.cmd`
- 데이터가 뭔가 비어 보인다, 테스트 데이터가 부족하다
  - `bootstrap.cmd`
- 테이블 구조가 꼬였거나 스키마 변경 직후다
  - `bootstrap.cmd --rebuild-schema`

기본 원칙:

- 모르면 먼저 `python bootstrap.py`
- DB 문제가 의심될 때만 `--initialize`
- 구조 재생성은 마지막 수단으로 `--rebuild-schema`

## 3. 안전 규칙

### 규칙 A. 빠른 실행은 DB를 건드리지 않는다

- `bootstrap-fast.cmd`는 안전 모드다.
- DB 초기화 관련 작업은 하지 않는다.

### 규칙 B. 데이터 재적재는 '부족할 때만' 한다

- 비교 기준: 예상 행 수(`EXPECTED_ROW_COUNTS`)
- 실제 행 수(`actual`)가 기대 행 수(`expected`)보다 작을 때만 재적재
- 조건식: `actual < expected`

### 규칙 C. 자동으로 더 강한 파괴 작업으로 넘어가지 않는다

- `TRUNCATE` 실패했다고 자동 `DROP` 하지 않는다.
- 시드 실패했다고 자동 `DROP` 하지 않는다.
- 이유: 실패 원인이 스키마가 아닐 수 있기 때문

## 4. 자주 나오는 용어를 쉽게 설명

- 부트스트랩(`bootstrap`)
  - 여러 서버/설치를 한 번에 처리하는 시작 스크립트
- 초기화(`--initialize`)
  - DB 상태를 확인하고, 필요하면 데이터를 다시 넣는 동작
- 스키마 재구성(`--rebuild-schema`)
  - 테이블 구조 자체를 다시 만드는 강한 초기화
- 데이터 비우기(`TRUNCATE`)
  - 테이블 구조는 두고 데이터만 비움
- 테이블 제거(`DROP`)
  - 테이블 구조까지 지움
- 시드(`seed`)
  - 테스트/기본 데이터를 DB에 넣는 작업
- 잠금 대기 제한시간(`lock_timeout`)
  - 락 때문에 무한 대기하지 않도록 제한하는 시간

## 5. bootstrap 관련 파일이 하는 일

- `bootstrap.py`
  - 전체 실행 조정(의존성 설치, 서버 실행, 종료)
  - 옵션(`--initialize` 등)에 따라 DB 스크립트 호출

- `bootstrap/shoppingmall.py`
  - ShoppingMall 백엔드 서버 실행 전용

- `bootstrap/farmos.py`
  - FarmOS 백엔드 서버 실행 전용

- `bootstrap/shoppingmall_seed.py`
  - 쇼핑몰 DB 점검/초기화 판단 + 핵심 데이터 시드

- `bootstrap/shoppingmall_review_seed.py`
  - 쇼핑몰 리뷰 1000건 시드

- `bootstrap/farmos_seed.py`
  - FarmOS DB 점검/초기화 판단 + 기본 계정/기본 테이블 시드

- `bootstrap/pesticide.py`
  - 농약 RAG 데이터 점검/적재(시드 계열)

## 6. 문제 상황별 대응

### 상황 1) Expected Row Count는 바꿨는데 시드 데이터 수정은 안 했다

증상:

- `--initialize`를 해도 계속 데이터 부족 판정

대응:

1. 자동 복구 기대하지 말고 실패 원인 로그 확인
2. 시드 코드/데이터를 먼저 수정
3. 다시 `--initialize` 실행

### 상황 2) 테이블 구조를 바꿨는데 시드 코드가 옛 구조를 사용한다

증상:

- INSERT/적재 중 SQL 오류 발생

대응:

1. 시드 코드와 스키마를 맞춘다
2. 필요하면 `--initialize --rebuild-schema`로 재구성
3. 자동 `DROP` 승격은 사용하지 않는다

### 상황 3) 다른 사람이 DB를 쓰는 중이라 초기화가 멈춘다

증상:

- 락 대기, timeout 에러

대응:

1. 잠금 해소 후 다시 실행
2. 팀 공지 후 초기화 시간대를 분리
3. `lock_timeout` 정책 유지(무한 대기 금지)

### 상황 4) PostgreSQL은 설치되어 있는데 Bootstrap에서 감지 실패

증상:

- `psql` 실행 파일을 찾지 못했다는 오류
- 또는 PostgreSQL 접속 확인 단계에서 즉시 실패

원인 후보:

1. PostgreSQL은 설치되어 있으나 `psql.exe` 경로가 PATH에 없음
2. `DATABASE_URL`이 현재 환경과 다른 호스트/포트를 가리킴
3. 서버는 켜져 있으나 접속 계정/비밀번호가 다름

대응:

1. `PSQL_EXE` 환경변수로 `psql.exe` 전체 경로를 지정하거나, PostgreSQL `bin` 경로를 PATH에 추가
2. `backend/.env`, `shopping_mall/backend/.env`의 `DATABASE_URL` 확인
3. 필요 시 하위 초기화 스크립트에 `--database-url`을 명시 전달해 검증

## 7. PR 반영 내용

- `bootstrap.py`에 `--rebuild-schema`를 명시적으로 노출
- `--rebuild-schema`는 `--initialize`와 함께만 허용
- 기본 경로는 안전 모드 유지(초기화 없음)
- 초기화 시 기본은 데이터 비우기(`TRUNCATE`) 우선
- PostgreSQL 클라이언트(`psql`)는 PATH 외 설치 경로/`PSQL_EXE`도 탐지
- 자동 승격(`TRUNCATE 실패 -> DROP`) 금지
- 로그 메시지에 "왜 실패했는지"를 더 명확히 표시

## 8. 팀 합의가 필요한 항목

- 운영 환경에서 `--rebuild-schema` 허용 여부
- `lock_timeout` 기본값(예: 5초/10초/30초)
- 재시도 횟수(권장: 0회 또는 매우 제한)
- 예상 행 수 기준을 하한(`>=`)으로 볼지, 정확 일치(`==`)로 볼지

## 9. 최종 정리

- 평소에는 `python bootstrap.py`만 사용한다.
- DB 문제가 있을 때만 `--initialize`를 사용한다.
- 스키마 재구성은 `--rebuild-schema`를 붙여 명시적으로 실행한다.
- 실패 시 자동으로 더 파괴적인 작업으로 넘어가지 않는다.
- Windows 사용자는 아래 두 래퍼로 선택 실행한다.
  - 빠른 모드: `bootstrap-fast.cmd`
  - DB 확인 포함 모드: `bootstrap.cmd`

이 원칙을 기준으로 bootstrap 코드를 단계적으로 정비한다.
