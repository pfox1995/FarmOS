# 네이버 스마트스토어 클론 - 쇼핑몰 프로젝트 기획서

## 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 프로젝트명 | Shopping Mall (네이버 스마트스토어 클론) |
| 목적 | 네이버 스마트스토어 UI/UX를 더미데이터 기반으로 구현 |
| 프로젝트 위치 | `shopping_mall/` (frontend + backend 분리) |
| 데이터 | 전체 더미데이터 (PostgreSQL 기반, `shop_` 접두사 테이블) |
| 시작일 | 2026-04-02 |

---

## 기술 스택

### Frontend (`shopping_mall/frontend/`) — port 5174
- **Framework**: React 19 + Vite (FarmOS 프론트엔드와 동일 스택)
- **Routing**: React Router DOM v7
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **State**: Zustand (장바구니, 사용자 상태)
- **Data Fetching**: TanStack Query + axios
- **Image**: Placeholder (picsum.photos)

### Backend (`shopping_mall/backend/`) — port 4000
- **Framework**: Python + FastAPI
- **ORM**: SQLAlchemy (sync mode)
- **Database**: PostgreSQL (`farmos` DB, `shop_` 접두사 테이블)
- **Package Manager**: uv
- **API Docs**: Swagger UI (자동, `/docs`)

---

## FarmOS 충돌 방지

| 항목 | FarmOS | Shopping Mall | 충돌 |
|------|--------|--------------|:----:|
| Backend port | 8000 | **4000** | No |
| Frontend port | 5173 | **5174** | No |
| Python venv | `backend/.venv` | `shopping_mall/backend/.venv` | No |
| node_modules | `frontend/` | `shopping_mall/frontend/` | No |
| DB | PostgreSQL (asyncpg) | **PostgreSQL (psycopg2, `shop_` 접두사)** | No |
| 패키지 매니저 | uv | uv (독립 lockfile) | No |

---

## 팀 에이전트 구성

```
        CTO Lead (opus) - 전체 조율
       ┌────────┼────────┐
  Frontend   Backend     DB
  React+Vite FastAPI    PostgreSQL
  UI/UX      더미 API   shop_ 테이블
```

---

## 핵심 페이지 목록

| 페이지 | 라우트 | 우선순위 |
|--------|--------|:--------:|
| 메인 페이지 | `/` | High |
| 상품 목록 | `/products` | High |
| 상품 상세 | `/products/:id` | High |
| 검색 결과 | `/search` | High |
| 장바구니 | `/cart` | High |
| 주문서 작성 | `/order` | Medium |
| 주문 완료 | `/order/complete` | Medium |
| 마이페이지 | `/mypage` | Medium |
| 주문 내역 | `/mypage/orders` | Medium |
| 찜 목록 | `/mypage/wishlist` | Medium |
| 판매자 스토어 | `/store/:id` | Low |

---

## API 엔드포인트 (FastAPI)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/products` | 상품 목록 (필터, 정렬, 페이지네이션) |
| GET | `/api/products/{id}` | 상품 상세 |
| GET | `/api/products/search` | 상품 검색 |
| GET | `/api/categories` | 카테고리 목록 |
| GET | `/api/cart` | 장바구니 조회 |
| POST | `/api/cart` | 장바구니 추가 |
| PUT | `/api/cart/{id}` | 장바구니 수량 변경 |
| DELETE | `/api/cart/{id}` | 장바구니 삭제 |
| POST | `/api/orders` | 주문 생성 |
| GET | `/api/orders` | 주문 내역 |
| GET | `/api/orders/{id}` | 주문 상세 |
| GET | `/api/reviews/product/{id}` | 상품 리뷰 |
| GET | `/api/stores/{id}` | 스토어 정보 |
| GET | `/api/users/me` | 내 정보 (더미) |
| GET/POST | `/api/wishlists` | 찜 목록 조회/토글 |

> Swagger UI: http://localhost:4000/docs

---

## PostgreSQL DB 테이블 (`shop_` 접두사)

| 테이블 | 주요 필드 | 시드 건수 |
|--------|----------|:---------:|
| shop_categories | id, name, parent_id, icon | 12 |
| shop_stores | id, name, description, rating | 5 |
| shop_products | id, name, price, discount_rate, category_id, store_id | 42 |
| shop_users | id, name, email, phone, address | 5 |
| shop_cart_items | id, user_id, product_id, quantity | 5 |
| shop_orders | id, user_id, total_price, status | 10 |
| shop_order_items | id, order_id, product_id, quantity, price | 19 |
| shop_reviews | id, product_id, user_id, rating, content | 30 |
| shop_wishlists | id, user_id, product_id | 8 |

---

## 구현 로드맵

### Phase 1: 기반 구축
- PostgreSQL 스키마 (`shop_` 접두사 테이블) + 시드 데이터
- FastAPI 서버 초기화 + 상품/카테고리 API

### Phase 2: 프론트엔드 코어
- React+Vite 프로젝트 초기화 + React Router + 레이아웃
- 메인 페이지 + 상품 목록/상세

### Phase 3: 쇼핑 플로우
- 장바구니 + 주문/결제

### Phase 4: 부가 기능
- 검색 + 마이페이지 + 리뷰

---

## 실행 방법

```bash
# Backend (port 4000)
cd shopping_mall/backend
uv sync
python ../../bootstrap/shoppingmall.py --mode init --skip-sync
uv run python main.py

# Frontend (port 5174)
cd shopping_mall/frontend
npm install && npm run dev

# 또는 전체 서비스 한번에 실행
bootstrap.cmd
```

