# FarmOS 개발환경 설정

## 시스템 요구사항

| 항목 | 버전 | 비고 |
|------|------|------|
| OS | Windows 11 Pro | |
| Node.js | v24.14.0 | 프론트엔드 |
| npm | 11.9.0 | |
| Python | 3.12.0 | 백엔드 |
| uv | 0.11.2 | Python 패키지 관리 |
| PostgreSQL | 18.3 | FarmOS + 쇼핑몰 공용 DB |

---

## 프로젝트 구조

```
FarmOS/
├── backend/           # FastAPI 백엔드
│   ├── app/
│   │   ├── api/       # 라우터 (auth, health, sensors, irrigation)
│   │   ├── core/      # 설정, DB, 보안, 저장소
│   │   ├── models/    # SQLAlchemy ORM 모델
│   │   └── schemas/   # Pydantic 스키마
│   ├── main.py        # uvicorn 진입점
│   ├── .env           # 환경 변수
│   └── pyproject.toml
├── frontend/          # React + Vite 프론트엔드
│   ├── src/
│   │   ├── components/layout/   # AppLayout, Sidebar, TopBar, MobileNav
│   │   ├── context/             # AuthContext, ScenarioContext
│   │   ├── hooks/               # useSensorData
│   │   ├── modules/             # auth, diagnosis, iot, 등 기능 모듈
│   │   ├── pages/               # DashboardPage, ScenarioPage
│   │   ├── mocks/               # Mock 데이터 (시나리오용)
│   │   └── types/               # TypeScript 인터페이스
│   ├── vite.config.ts
│   └── package.json
├── shopping_mall/     # 쇼핑몰 모듈 (독립 패키지)
│   ├── backend/       # FastAPI (port 4000, sync SQLAlchemy + psycopg2)
│   │   ├── app/       # 라우터, 모델, 스키마, 서비스
│   │   ├── db/        # DB 모듈
│   │   └── .env       # DB 접속 정보
│   └── frontend/      # React + Vite (port 5174)
├── docs/              # 프로젝트 문서
└── tools/             # 유틸리티
```

---

## 1. PostgreSQL 설정

### DB 생성

```sql
-- psql -U postgres 접속 후
CREATE DATABASE farmos;
```

### 접속 정보

| 항목 | 값 |
|------|-----|
| Host | localhost |
| Port | 5432 |
| User | postgres |
| Password | root |
| Database | farmos |

> 테이블은 서버 시작 시 자동 생성됨 (SQLAlchemy `create_all`)

---

## 2. 백엔드 설정

### 의존성 설치

```bash
cd backend
uv sync
```

### 환경 변수 (.env)

```env
DATABASE_URL=postgresql+asyncpg://postgres:root@localhost:5432/farmos
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]
SOIL_MOISTURE_LOW=55.0
SOIL_MOISTURE_HIGH=70.0
```

### 서버 실행

```bash
cd backend
uv run python main.py
```

- 서버: http://localhost:8000
- Swagger 문서: http://localhost:8000/docs
- 시작 시 자동으로 테이블 생성 + 테스트 계정 시딩

### 주요 의존성

| 패키지 | 용도 |
|--------|------|
| fastapi | 웹 프레임워크 |
| uvicorn | ASGI 서버 |
| sqlalchemy[asyncio] | ORM (async) |
| asyncpg | PostgreSQL async 드라이버 |
| python-jose | JWT 토큰 |
| bcrypt | 비밀번호 해싱 |
| pydantic-settings | 환경 변수 관리 |

---

## 3. 프론트엔드 설정

### 의존성 설치

```bash
cd frontend
npm install
```

### 개발 서버 실행

```bash
cd frontend
npm run dev
```

- 서버: http://localhost:5173
- path alias: `@` → `src/`

### 주요 의존성

| 패키지 | 용도 |
|--------|------|
| react 19 | UI 프레임워크 |
| react-router-dom 7 | 라우팅 |
| tailwindcss 4 | 스타일링 |
| framer-motion | 애니메이션 |
| recharts | 차트 |
| react-hot-toast | 알림 토스트 |
| react-icons | 아이콘 |

### 빌드

```bash
npm run build    # 프로덕션 빌드
npm run preview  # 빌드 결과 미리보기
```

---

## 4. 테스트 계정

| 아이디 | 비밀번호 | 이름 | 지역 |
|--------|----------|------|------|
| farmer01 | farm1234 | 김사과 | 경북 영주시 |
| parkpear | pear5678 | 박배나무 | 충남 천안시 |

---

## 5. API 기본 경로

Base URL: `http://localhost:8000/api/v1`

| 그룹 | 경로 | 저장소 |
|------|------|--------|
| 인증 | `/auth/*` | PostgreSQL |
| 헬스체크 | `/health` | 인메모리 |
| 센서 | `/sensors/*` | 인메모리 |
| 관개 | `/irrigation/*` | 인메모리 |

### 쇼핑몰 API (port 4000)

Base URL: `http://localhost:4000/api`

| 그룹 | 경로 | 저장소 |
|------|------|--------|
| 상품 | `/products/*` | PostgreSQL (`shop_` 테이블) |
| 카테고리 | `/categories/*` | PostgreSQL (`shop_` 테이블) |
| 장바구니 | `/cart/*` | PostgreSQL (`shop_` 테이블) |
| 주문 | `/orders/*` | PostgreSQL (`shop_` 테이블) |
| 백오피스 | `/shipments/*`, `/reports/*`, `/analytics/*` | PostgreSQL (`shop_` 테이블) |

---

## 6. 쇼핑몰 설정

### 의존성 설치

```bash
cd shopping_mall/backend
uv sync

cd shopping_mall/frontend
npm install
```

### 환경 변수 (`shopping_mall/backend/.env`)

```env
DATABASE_URL=postgresql+psycopg2://postgres:root@localhost:5432/farmos
```

### 시드 데이터 투입

```bash
cd shopping_mall/backend
python ../../bootstrap/shoppingmall.py --mode init --skip-sync
```

### 서버 실행

```bash
# 쇼핑몰 백엔드 (port 4000)
cd shopping_mall/backend && uv run python main.py

# 쇼핑몰 프론트엔드 (port 5174)
cd shopping_mall/frontend && npm run dev
```

> 쇼핑몰 테이블은 FarmOS와 같은 `farmos` DB를 사용하며, `shop_` 접두사로 구분됩니다.

---

## 7. 동시 실행 (개발 시)

`start-all.bat`으로 4개 서버를 한번에 실행:

```bash
start-all.bat
```

| 서비스 | 주소 |
|--------|------|
| FarmOS Backend | http://localhost:8000 |
| FarmOS Frontend | http://localhost:5173 |
| Shop Backend | http://localhost:4000 |
| Shop Frontend | http://localhost:5174 |

종료: 아무 키를 누르면 모든 서버가 한번에 종료됩니다.

