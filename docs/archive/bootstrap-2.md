# bootstrap

# Bootstrap 쉬운 안내서 (초심자용)

---

## 1. 제일 많이 쓰는 명령

### 1) 평소 개발 시작(가장 자주 사용)

```bash
python bootstrap.py
```

- 하는 일: 의존성 확인/설치 + 서버 실행 전 데이터베이스 상태 확인 (내부 데이터, 데이터베이스, 테이블) → 서버 실행.

---

## 2. 자주 나오는 용어를 쉽게 설명

- 부트스트랩(`bootstrap`)
    - 여러 서버/설치를 한 번에 처리하는 시작 스크립트
- 데이터 비우기(`TRUNCATE`)
    - 테이블 구조는 두고 데이터만 비움
- 테이블 제거(`DROP`)
    - 테이블 구조까지 지움
- 시드(`seed`)
    - 테스트/기본 데이터를 DB에 넣는 작업
- 잠금 대기 제한시간(`lock_timeout`)
    - 락 때문에 무한 대기하지 않도록 제한하는 시간

---

## 3. bootstrap 관련 파일이 하는 일

- `bootstrap.py`
    - 전체 실행 조정(의존성 설치, 서버 실행, 종료)
- `bootstrap/shoppingmall.py`
    - 쇼핑몰 테이블 점검/초기화 판단
- `bootstrap/farmos.py`
    - FarmOS 테이블 점검/초기화 판단
- `bootstrap/shoppingmall_seed.py`
    - 쇼핑몰 핵심 데이터 시드
- `bootstrap/shoppingmall_review_seed.py`
    - 쇼핑몰 리뷰 1000건 시드
- `bootstrap/farmos_seed.py`
    - FarmOS 기본 계정/기본 테이블 시드
- `bootstrap/pesticide.py`
    - 농약 RAG 데이터 적재

---

## 4. 문제 상황별 대응

### 상황 1) Expected Row Count는 바꿨는데 시드 데이터 수정은 안 했다

대응:

1. 자동 복구 기대하지 말고 실패 원인 로그 확인
2. 시드 코드/데이터를 먼저 수정 전, 토의 후 변경사항을 보고.
3. 코드 수정 후 ORM이 자동으로 수행되게 진행.

### 상황 2) 테이블 구조를 바꿨는데 시드 코드가 옛 구조를 사용한다

증상:

- INSERT/적재 중 SQL 오류 발생

대응:

1. 시드 코드와 스키마를 ORM을 통해서 맞춰주고 PR후 Merge 진행
