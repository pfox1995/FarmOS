# Shopping Mall (네이버 스마트스토어 클론) Planning Document

> **Summary**: 네이버 스마트스토어와 유사한 쇼핑몰을 Python(FastAPI) + PostgreSQL + React(Vite)로 구현 (더미데이터)
>
> **Project**: FarmOS - Shopping Mall Module
> **Version**: 0.3.0
> **Author**: clover0309
> **Date**: 2026-04-02
> **Status**: Draft

---

## Executive Summary

| Perspective | Content |
|-------------|---------|
| **Problem** | 스마트스토어 형태의 쇼핑몰 UI/UX를 빠르게 프로토타이핑할 수 있는 프론트엔드가 필요하다 |
| **Solution** | React+Vite 프론트엔드 + FastAPI(Python) 더미 API 서버 + PostgreSQL(`shop_` 접두사 테이블)로 구성, `shopping_mall/` 독립 패키지로 개발 |
| **Function/UX Effect** | 상품 목록/검색/상세/장바구니/주문 등 핵심 쇼핑 플로우를 네이버 스마트스토어 UI와 유사하게 제공 |
| **Core Value** | 기존 FarmOS와 완전 격리된 환경에서 더미데이터 기반 쇼핑몰을 빠르게 검증, 추후 실제 백엔드 교체 용이 |

---

## 1. Overview

### 1.1 Purpose

네이버 스마트스토어와 유사한 쇼핑몰 프론트엔드를 React+Vite로 구축한다. 백엔드는 Python + FastAPI로, 데이터베이스는 PostgreSQL(FarmOS와 동일 `farmos` DB, `shop_` 접두사 테이블)로 구성하며, 모든 데이터는 더미데이터로 처리한다.

### 1.2 Background

- FarmOS 프로젝트 내 쇼핑몰 모듈로서 농산물 직거래/판매 기능 검증 목적
- 기존 FarmOS의 `frontend/`(React+Vite), `backend/`(FastAPI, port 8000)와 **완전 독립**
- `shopping_mall/` 하위에 별도 패키지로 구성하여 의존성/포트/가상환경 모두 분리
- FarmOS와 동일한 PostgreSQL DB를 공유하되 `shop_` 접두사로 테이블 격리

### 1.3 Related Documents

- 참고: 네이버 스마트스토어 (https://smartstore.naver.com)
- FarmOS 백엔드 구조: `backend/pyproject.toml` (FastAPI, port 8000, asyncpg)
- FarmOS 프론트엔드 구조: `frontend/package.json` (React+Vite, port 5173)

---

## 2. FarmOS 충돌 방지 전략

### 2.1 충돌 위험 분석

| 항목 | FarmOS 현재 사용 | Shopping Mall 계획 | 충돌 가능성 | 대응 |
|------|-----------------|-------------------|:-----------:|------|
| **Backend 포트** | `8000` (uvicorn) | `4000` (uvicorn) | High | 포트 분리 (4000) |
| **Frontend 포트** | `5173` (Vite) | `5174` (Vite) | High | 포트 분리 (5174) |
| **Python 가상환경** | `backend/.venv` (uv) | `shopping_mall/backend/.venv` (uv) | Medium | 독립 venv, 별도 pyproject.toml |
| **node_modules** | `frontend/node_modules` | `shopping_mall/frontend/node_modules` | None | 각자 독립 |
| **PostgreSQL DB 파일** | 없음 (asyncpg/PostgreSQL) | `shopping_mall/backend/db/farmos DB (shop_ 접두사 테이블)` | None | 경로 분리 |
| **Git 추적** | `.gitignore` 루트 | shopping_mall 전용 `.gitignore` 추가 | Low | `.db`, `.venv`, `node_modules` 제외 |
| **Python 버전** | 3.12+ (`backend/.python-version`) | 3.12+ (동일) | None | 호환 |
| **패키지 매니저** | uv | uv | None | 동일 도구, 별도 lockfile |

### 2.2 격리 원칙

1. **폴더 완전 분리**: `shopping_mall/` 하위에 모든 코드/설정/DB 포함
2. **포트 충돌 방지**: FarmOS(8000/5173) vs Shopping Mall(4000/5174) 명확 분리
3. **가상환경 독립**: 각자의 `.venv`, `pyproject.toml`, `uv.lock` 보유
4. **DB 파일 격리**: PostgreSQL 파일은 `shopping_mall/backend/db/` 내부에만 존재
5. **환경변수 분리**: `.env` 파일 각 패키지 내부에 독립 관리
6. **스크립트 독립**: `shopping_mall/` 루트에 전용 실행 스크립트 제공

---

## 3. Scope

### 3.1 In Scope

- [ ] 메인 페이지 (배너, 추천 상품, 카테고리 네비게이션)
- [ ] 상품 목록 페이지 (카테고리별 필터링, 정렬, 페이지네이션)
- [ ] 상품 검색 (키워드 검색, 자동완성)
- [ ] 상품 상세 페이지 (이미지 갤러리, 옵션 선택, 리뷰, 상품 정보)
- [ ] 장바구니 (추가/삭제/수량변경, 선택 주문)
- [ ] 주문/결제 페이지 (주문서 작성, 결제 시뮬레이션)
- [ ] 주문 완료 / 주문 내역 페이지
- [ ] 마이페이지 (주문 내역, 찜 목록, 회원 정보)
- [ ] 판매자 스토어 페이지
- [ ] FastAPI 더미 API 서버
- [ ] PostgreSQL 더미 DB + 시드 데이터

### 3.2 Out of Scope

- 실제 결제 연동 (PG사)
- 실제 사용자 인증 (OAuth, 소셜 로그인)
- 외부 데이터베이스 연동 (PostgreSQL, MySQL 등)
- 관리자 대시보드
- 채팅/문의 기능
- 배송 추적 연동

---

## 4. Requirements

### 4.1 Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-01 | 메인 페이지: 배너 슬라이더, 추천 상품, 카테고리 메뉴 | High | Pending |
| FR-02 | 상품 목록: 카테고리별 필터, 가격/인기순 정렬, 페이지네이션 | High | Pending |
| FR-03 | 상품 검색: 키워드 검색, 검색 결과 페이지, 자동완성 | High | Pending |
| FR-04 | 상품 상세: 이미지 갤러리, 옵션 선택, 수량 선택, 장바구니/바로구매 | High | Pending |
| FR-05 | 장바구니: 상품 추가/삭제/수량변경, 전체/선택 삭제, 가격 합계 | High | Pending |
| FR-06 | 주문/결제: 배송지 입력, 결제수단 선택 (시뮬레이션), 주문 확인 | Medium | Pending |
| FR-07 | 주문 완료/내역: 주문 완료 안내, 주문 내역 리스트, 주문 상세 | Medium | Pending |
| FR-08 | 마이페이지: 주문 내역, 찜 목록, 최근 본 상품, 회원 정보 | Medium | Pending |
| FR-09 | 판매자 스토어: 스토어 프로필, 스토어 상품 목록 | Low | Pending |
| FR-10 | 상품 리뷰: 리뷰 목록 표시, 별점 표시 (더미) | Medium | Pending |
| FR-11 | FastAPI 더미 API 서버: RESTful 엔드포인트 + Swagger UI | High | Pending |
| FR-12 | PostgreSQL DB: 테이블 스키마 설계 + 시드 데이터 자동 생성 | High | Pending |

### 4.2 Non-Functional Requirements

| Category | Criteria | Measurement Method |
|----------|----------|-------------------|
| Performance | 페이지 로드 < 2s (더미데이터 기준) | Lighthouse |
| Responsive | 모바일/태블릿/데스크톱 반응형 지원 | Chrome DevTools |
| Browser | Chrome, Edge, Safari 최신 버전 지원 | 수동 테스트 |
| Code Quality | TypeScript strict mode (FE), Python type hints (BE) | TSC / mypy |
| API Docs | Swagger UI 자동 생성 | FastAPI /docs |

---

## 5. Success Criteria

### 5.1 Definition of Done

- [ ] 모든 FR-01 ~ FR-12 기능 구현 완료
- [ ] 모바일/데스크톱 반응형 동작 확인
- [ ] 더미데이터로 전체 쇼핑 플로우 (검색 -> 상세 -> 장바구니 -> 주문) 동작
- [ ] FarmOS 백엔드(port 8000)와 동시 실행 시 충돌 없음
- [ ] PDCA Gap Analysis Match Rate >= 90%

### 5.2 Quality Criteria

- [ ] TypeScript 컴파일 에러 없음 (Frontend)
- [ ] Python 타입 힌트 일관성 (Backend)
- [ ] ESLint 경고/에러 없음 (Frontend)
- [ ] 빌드 성공 (Frontend + Backend)

---

## 6. Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| FarmOS 백엔드와 포트 충돌 | High | Medium | 포트 4000 사용, `.env`로 관리 |
| Python 가상환경 혼동 | Medium | Medium | 독립 `.venv`, `pyproject.toml` 분리, README에 실행법 명시 |
| PostgreSQL 동시 접근 제한 | Low | Low | 더미데이터 규모에서는 문제 없음, WAL 모드 활성화 |
| 프론트엔드 규모 과대 | Medium | Low | MVP 범위 우선 구현, 후속 PDCA |

---

## 7. Architecture Considerations

### 7.1 Project Level Selection

| Level | Characteristics | Recommended For | Selected |
|-------|-----------------|-----------------|:--------:|
| **Starter** | Simple structure | Static sites, portfolios | ☐ |
| **Dynamic** | Feature-based modules, API integration | Web apps with backend | ☑ |
| **Enterprise** | Strict layer separation, DI, microservices | High-traffic systems | ☐ |

### 7.2 Key Architectural Decisions

| Decision | Options | Selected | Rationale |
|----------|---------|----------|-----------|
| Frontend Framework | Next.js / React+Vite / Vue | **React 19 + Vite** | 기존 FarmOS 프론트엔드와 동일 스택, 빌드 속도 우수 |
| State Management | Context / Zustand / Redux | **Zustand** | 경량, 장바구니 상태 관리 적합 |
| Styling | Tailwind / CSS Modules / styled | **Tailwind CSS** | 빠른 프로토타이핑, 유틸리티 기반 |
| Backend Framework | FastAPI / Flask / Django | **FastAPI** | 비동기, 자동 Swagger, 타입 안전, FarmOS와 동일 스택 |
| Database | PostgreSQL / PostgreSQL / JSON | **PostgreSQL** | 설치 불필요, 파일 기반, SQL 쿼리 지원 |
| ORM | SQLAlchemy / Tortoise / Raw SQL | **SQLAlchemy (sync)** | FarmOS와 동일 ORM, 풍부한 생태계 |
| API Client | fetch / axios / TanStack Query | **axios + TanStack Query** | 캐싱, 로딩/에러 상태 자동 관리 |
| Routing | React Router / TanStack Router | **React Router DOM v7** | FarmOS와 동일, SPA 라우팅 |
| Image Handling | img + placeholder / 외부 라이브러리 | **img + Placeholder 이미지 (picsum)** | 더미데이터용 무료 이미지 |
| Package Manager (Python) | uv / pip / poetry | **uv** | FarmOS와 동일, 빠른 설치 |

### 7.3 프로젝트 폴더 구조

```
FarmOS/                              # 기존 프로젝트 루트
├── frontend/                        # [기존] FarmOS 프론트엔드 (React+Vite, port 5173)
├── backend/                         # [기존] FarmOS 백엔드 (FastAPI, port 8000)
├── tools/                           # [기존] FarmOS 도구
│
├── shopping_mall/                   # [신규] 쇼핑몰 전용 폴더
│   │
│   ├── frontend/                    # React+Vite 프론트엔드 패키지 (port 5174)
│   │   ├── package.json
│   │   ├── vite.config.ts
│   │   ├── tailwind.config.ts
│   │   ├── tsconfig.json
│   │   ├── index.html
│   │   ├── .env                     # VITE_API_URL=http://localhost:4000
│   │   ├── .gitignore
│   │   ├── public/
│   │   │   └── images/
│   │   └── src/
│   │       ├── router.tsx               # React Router 설정
│   │       ├── pages/                   # React Router 페이지
│   │       │   ├── HomePage.tsx                 # 메인 페이지
│   │       │   ├── ProductListPage.tsx          # 상품 목록
│   │       │   ├── ProductDetailPage.tsx        # 상품 상세
│   │       │   ├── SearchPage.tsx               # 검색 결과
│   │       │   ├── CartPage.tsx                 # 장바구니
│   │       │   ├── OrderPage.tsx                # 주문서 작성
│   │       │   ├── OrderCompletePage.tsx        # 주문 완료
│   │       │   ├── MyPage.tsx                   # 마이페이지
│   │       │   ├── MyOrdersPage.tsx             # 주문 내역
│   │       │   ├── WishlistPage.tsx             # 찜 목록
│   │       │   └── StorePage.tsx                # 판매자 스토어
│   │       ├── components/
│   │       │   ├── common/           # Header, Footer, Button, SearchBar
│   │       │   ├── home/             # Banner, RecommendSection, CategoryNav
│   │       │   ├── product/          # ProductCard, ImageGallery, OptionSelector
│   │       │   ├── cart/             # CartItem, CartSummary
│   │       │   ├── order/            # OrderForm, PaymentSelector
│   │       │   └── review/           # ReviewList, StarRating
│   │       ├── stores/               # Zustand 스토어
│   │       │   ├── cartStore.ts
│   │       │   ├── userStore.ts
│   │       │   └── searchStore.ts
│   │       ├── hooks/                # 커스텀 훅
│   │       │   ├── useProducts.ts
│   │       │   ├── useCart.ts
│   │       │   └── useOrders.ts
│   │       ├── lib/                  # 유틸리티
│   │       │   ├── api.ts            # axios 인스턴스 (baseURL: localhost:4000)
│   │       │   └── utils.ts          # 가격 포맷터, 날짜 헬퍼
│   │       └── types/                # TypeScript 타입
│   │           ├── product.ts
│   │           ├── order.ts
│   │           ├── user.ts
│   │           └── cart.ts
│   │
│   └── backend/                      # FastAPI 더미 API 서버 (port 4000)
│       ├── pyproject.toml            # 독립 Python 패키지 설정
│       ├── .python-version           # 3.12
│       ├── .env                      # PORT=4000, DATABASE_URL=postgresql+psycopg2://postgres:root@localhost:5432/farmos
│       ├── .gitignore                # .venv, db/*.db, __pycache__
│       ├── main.py                   # uvicorn 진입점
│       ├── db/
│       │   ├── farmos DB (shop_ 접두사 테이블)               # PostgreSQL DB 파일 (git 제외)
│       │   └── seed.py               # 더미 데이터 시드 스크립트
│       └── app/
│           ├── __init__.py
│           ├── main.py               # FastAPI 앱 생성, 라우터 등록
│           ├── database.py           # SQLAlchemy 엔진/세션 (PostgreSQL)
│           ├── models/               # SQLAlchemy 모델
│           │   ├── __init__.py
│           │   ├── product.py
│           │   ├── category.py
│           │   ├── user.py
│           │   ├── order.py
│           │   ├── review.py
│           │   └── store.py
│           ├── schemas/              # Pydantic 스키마
│           │   ├── __init__.py
│           │   ├── product.py
│           │   ├── category.py
│           │   ├── user.py
│           │   ├── order.py
│           │   ├── review.py
│           │   └── store.py
│           ├── routers/              # API 라우터
│           │   ├── __init__.py
│           │   ├── products.py
│           │   ├── categories.py
│           │   ├── cart.py
│           │   ├── orders.py
│           │   ├── users.py
│           │   ├── reviews.py
│           │   └── stores.py
│           └── crud/                 # CRUD 로직
│               ├── __init__.py
│               ├── product.py
│               ├── category.py
│               ├── order.py
│               └── review.py
│
└── docs/
    └── 01-plan/features/
        └── shopping-mall.plan.md     # 이 문서
```

---

## 8. PostgreSQL DB 스키마 설계

### 8.1 테이블 구조

```sql
-- 카테고리
CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    parent_id INTEGER REFERENCES categories(id),
    icon TEXT,
    sort_order INTEGER DEFAULT 0
);

-- 스토어 (판매자)
CREATE TABLE stores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    image_url TEXT,
    rating REAL DEFAULT 0.0,
    product_count INTEGER DEFAULT 0
);

-- 상품
CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    price INTEGER NOT NULL,              -- 원 단위
    discount_rate INTEGER DEFAULT 0,     -- % 할인율
    category_id INTEGER REFERENCES categories(id),
    store_id INTEGER REFERENCES stores(id),
    thumbnail TEXT,
    images TEXT,                          -- JSON array
    options TEXT,                         -- JSON array (색상, 사이즈 등)
    stock INTEGER DEFAULT 100,
    rating REAL DEFAULT 0.0,
    review_count INTEGER DEFAULT 0,
    sales_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 사용자
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    address TEXT,                         -- JSON (우편번호, 주소, 상세주소)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 장바구니
CREATE TABLE cart_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    product_id INTEGER REFERENCES products(id),
    quantity INTEGER DEFAULT 1,
    selected_option TEXT,                 -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 주문
CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    total_price INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',        -- pending, paid, shipping, delivered, cancelled
    shipping_address TEXT,                -- JSON
    payment_method TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 주문 상품
CREATE TABLE order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER REFERENCES orders(id),
    product_id INTEGER REFERENCES products(id),
    quantity INTEGER NOT NULL,
    price INTEGER NOT NULL,
    selected_option TEXT                  -- JSON
);

-- 리뷰
CREATE TABLE reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER REFERENCES products(id),
    user_id INTEGER REFERENCES users(id),
    rating INTEGER NOT NULL,             -- 1~5
    content TEXT,
    images TEXT,                          -- JSON array
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 찜 목록
CREATE TABLE wishlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    product_id INTEGER REFERENCES products(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, product_id)
);
```

### 8.2 시드 데이터 규모

| 엔티티 | 건수 | 비고 |
|--------|:----:|------|
| categories | 12 | 2단계 계층 (대분류 4 + 소분류 8) |
| stores | 5 | 판매자 스토어 |
| products | 40+ | 카테고리당 약 10개 |
| users | 5 | 테스트 사용자 |
| reviews | 30+ | 상품당 평균 3-5개 |
| orders | 10 | 다양한 상태 포함 |

---

## 9. API 엔드포인트 설계

| Method | Endpoint | 설명 | 비고 |
|--------|----------|------|------|
| GET | `/api/products` | 상품 목록 (필터, 정렬, 페이지네이션) | query: category, sort, page, limit |
| GET | `/api/products/{id}` | 상품 상세 | |
| GET | `/api/products/search` | 상품 검색 | query: q, page, limit |
| GET | `/api/categories` | 카테고리 목록 (트리 구조) | |
| GET | `/api/categories/{id}/products` | 카테고리별 상품 | |
| GET | `/api/cart` | 장바구니 조회 | header: X-User-Id (더미 인증) |
| POST | `/api/cart` | 장바구니 추가 | |
| PUT | `/api/cart/{id}` | 장바구니 수량 변경 | |
| DELETE | `/api/cart/{id}` | 장바구니 삭제 | |
| POST | `/api/orders` | 주문 생성 | |
| GET | `/api/orders` | 주문 내역 | |
| GET | `/api/orders/{id}` | 주문 상세 | |
| GET | `/api/reviews/product/{id}` | 상품 리뷰 | |
| GET | `/api/stores/{id}` | 스토어 정보 | |
| GET | `/api/stores/{id}/products` | 스토어 상품 목록 | |
| GET | `/api/users/me` | 내 정보 | 더미 사용자 반환 |
| GET | `/api/wishlists` | 찜 목록 | |
| POST | `/api/wishlists/{product_id}` | 찜 추가/삭제 (토글) | |

> Swagger UI: `http://localhost:4000/docs`에서 자동 확인 가능

---

## 10. Convention Prerequisites

### 10.1 Existing Project Conventions

- [x] ESLint configuration (`eslint.config.js` - 기존 FarmOS frontend에서 참조)
- [x] TypeScript configuration (`tsconfig.json` - 기존 FarmOS)
- [x] Python 패키지 관리 (`uv` - 기존 FarmOS backend과 동일)
- [ ] shopping_mall/frontend 전용 ESLint/Prettier 설정 필요
- [ ] shopping_mall/backend 전용 pyproject.toml 설정 필요

### 10.2 Conventions to Define/Verify

| Category | Current State | To Define | Priority |
|----------|---------------|-----------|:--------:|
| **FE Naming** | missing | 컴포넌트: PascalCase, 훅: camelCase (use-prefix), 파일: kebab-case | High |
| **BE Naming** | missing | 모듈: snake_case, 클래스: PascalCase, 함수: snake_case | High |
| **Folder structure** | missing | 위 7.3 구조 따름 | High |
| **FE Import order** | missing | 1.React 2.react-router 3.외부 4.내부 5.타입 6.스타일 | Medium |
| **BE Import order** | missing | 1.stdlib 2.third-party 3.local | Medium |

### 10.3 Environment Variables Needed

| Variable | Purpose | Package | Default |
|----------|---------|---------|---------|
| `VITE_API_URL` | 더미 API 서버 주소 | frontend | `http://localhost:4000` |
| `PORT` | Backend 서버 포트 | backend | `4000` |
| `DATABASE_URL` | PostgreSQL DB 경로 | backend | `postgresql+psycopg2://postgres:root@localhost:5432/farmos` |

---

## 11. Team Agent 구성

### 11.1 팀 구조

```
        CTO Lead (opus) - 전체 아키텍처/PDCA 조율
       ┌────────┼────────┐
  Frontend   Backend     DB
   Agent      Agent     Agent
React+Vite  FastAPI    PostgreSQL
  UI/UX      API 서버   스키마/시드
  Zustand    라우터      더미데이터
```

| Role | Agent Type | 담당 영역 |
|------|-----------|----------|
| **CTO Lead** | cto-lead (opus) | 전체 아키텍처 결정, PDCA 워크플로우 조율, 충돌 방지 감독 |
| **Frontend** | frontend-architect | React+Vite UI 구현, 컴포넌트 설계, Zustand 상태 관리 |
| **Backend** | bkend-expert | FastAPI 더미 API 서버, 라우터/CRUD 설계 |
| **DB** | product-manager | PostgreSQL 스키마 설계, 시드 데이터 생성, 데이터 관계 설계 |

### 11.2 팀별 작업 분배

**DB 팀:**
1. PostgreSQL 테이블 스키마 정의 (models/)
2. Pydantic 스키마 정의 (schemas/)
3. 시드 데이터 스크립트 작성 (db/seed.py)
4. 더미 데이터 생성 (40+ 상품, 12 카테고리, 5 스토어, 5 사용자, 30+ 리뷰)

**Backend 팀:**
1. FastAPI 프로젝트 초기화 (`pyproject.toml`, `main.py`)
2. SQLAlchemy + PostgreSQL 연결 설정 (`database.py`)
3. API 라우터 구현 (routers/)
4. CRUD 로직 구현 (crud/)
5. CORS 설정, 에러 핸들링
6. 페이지네이션, 필터링, 정렬 로직

**Frontend 팀:**
1. React+Vite 프로젝트 초기화 + React Router 설정
2. 공통 컴포넌트 (Header, Footer, Layout, SearchBar)
3. 메인 페이지 (배너, 추천 상품, 카테고리)
4. 상품 목록/상세 페이지
5. 장바구니/주문 페이지
6. 마이페이지/검색

---

## 12. 구현 순서 (Implementation Roadmap)

### Phase 1: 기반 구축 (DB + Backend)
1. `shopping_mall/backend/` 프로젝트 초기화 (pyproject.toml, uv)
2. SQLAlchemy 모델 정의 + PostgreSQL 연결
3. 시드 데이터 스크립트 작성 및 실행
4. 핵심 API 구현 (상품 목록/상세, 카테고리)
5. Swagger UI 확인

### Phase 2: 프론트엔드 코어 (Frontend)
1. `shopping_mall/frontend/` React+Vite 프로젝트 초기화
2. 공통 레이아웃 (Header, Footer, Navigation)
3. 메인 페이지 (배너, 카테고리, 추천 상품)
4. 상품 목록/상세 페이지 + API 연동

### Phase 3: 쇼핑 플로우 (Frontend + Backend)
1. 장바구니 API + UI (Zustand 연동)
2. 주문/결제 페이지 (시뮬레이션)
3. 주문 완료/내역 페이지

### Phase 4: 부가 기능
1. 검색 기능 (자동완성)
2. 마이페이지 (주문 내역, 찜 목록)
3. 판매자 스토어 페이지
4. 상품 리뷰 표시

---

## 13. 실행 가이드

### Backend 실행
```bash
cd shopping_mall/backend
uv venv                     # 가상환경 생성
uv sync                     # 의존성 설치
python db/seed.py            # 더미 데이터 시드
python main.py               # http://localhost:4000 (Swagger: /docs)
```

### Frontend 실행
```bash
cd shopping_mall/frontend
npm install                  # 의존성 설치
npm run dev                  # http://localhost:5174
```

### FarmOS와 동시 실행 확인
```
FarmOS Backend:        http://localhost:8000  (기존)
FarmOS Frontend:       http://localhost:5173  (기존)
Shopping Mall Backend: http://localhost:4000  (신규)
Shopping Mall Frontend: http://localhost:5174  (신규)
```

---

## 14. Next Steps

1. [ ] Design 문서 작성 (`shopping-mall.design.md`)
2. [ ] 팀 리뷰 및 승인
3. [ ] Phase 1 구현 시작 (DB 스키마 + FastAPI 초기화)

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-04-02 | Initial draft (Express + JSON) | clover0309 |
| 0.2 | 2026-04-02 | Stack change: Python + FastAPI + PostgreSQL, FarmOS 충돌 방지 전략 추가 | clover0309 |
| 0.3 | 2026-04-02 | Stack change: Next.js → React+Vite, FarmOS 프론트엔드 스택 통일 | clover0309 |
