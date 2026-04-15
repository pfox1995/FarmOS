# Shopping Mall Design Document

> **Summary**: 네이버 스마트스토어 클론 쇼핑몰 — React(Vite) + FastAPI + PostgreSQL 상세 설계
>
> **Project**: FarmOS - Shopping Mall Module
> **Version**: 0.1.0
> **Author**: clover0309
> **Date**: 2026-04-02
> **Status**: Draft
> **Planning Doc**: [shopping-mall.plan.md](../01-plan/features/shopping-mall.plan.md)

---

## 1. Overview

### 1.1 Design Goals

- 네이버 스마트스토어와 유사한 쇼핑 경험을 프론트엔드에서 구현
- 더미데이터 기반이지만 실제 서비스 수준의 API 구조를 갖춘 백엔드
- FarmOS(port 8000/5173)와 완전 격리된 독립 실행 환경
- 추후 실제 DB/인증 교체 시 최소 변경으로 전환 가능한 구조

### 1.2 Design Principles

- **관심사 분리**: Frontend(UI) / Backend(API) / DB(데이터) 계층 명확 분리
- **독립 패키지**: `shopping_mall/frontend`와 `shopping_mall/backend`는 각자 독립 실행
- **타입 안전**: Frontend(TypeScript strict), Backend(Python type hints + Pydantic)
- **더미 투명성**: 더미 인증은 `X-User-Id` 헤더로 단순 처리, 추후 JWT 교체 용이

---

## 2. Architecture

### 2.1 시스템 아키텍처

```
┌──────────────────────────────────────────────────────────────┐
│                        User (Browser)                        │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│              Frontend (React 19 + Vite, port 5174)              │
│  ┌─────────┐  ┌──────────┐  ┌────────┐  ┌───────────────┐  │
│  │  Pages  │  │Components│  │ Stores │  │ Hooks/Queries │  │
│  │(React   │  │(common/  │  │(Zustand│  │(TanStack      │  │
│  │ Router) │  │ product/ │  │ cart,  │  │ Query +       │  │
│  │         │  │ cart/    │  │ user)  │  │ axios)        │  │
│  │         │  │ order/)  │  │        │  │               │  │
│  └─────────┘  └──────────┘  └────────┘  └───────┬───────┘  │
│                                                  │          │
└──────────────────────────────────────────────────┼──────────┘
                                                   │ HTTP (REST)
                                                   │ localhost:4000
┌──────────────────────────────────────────────────▼──────────┐
│              Backend (FastAPI, port 4000)                    │
│  ┌─────────┐  ┌──────────┐  ┌────────┐  ┌──────────────┐  │
│  │ Routers │  │  CRUD    │  │Schemas │  │   Models     │  │
│  │(products│  │(product, │  │(Pydan- │  │(SQLAlchemy)  │  │
│  │ cart,   │  │ order,   │  │ tic)   │  │              │  │
│  │ orders) │  │ review)  │  │        │  │              │  │
│  └─────────┘  └──────────┘  └────────┘  └──────┬───────┘  │
│                                                  │          │
└──────────────────────────────────────────────────┼──────────┘
                                                   │ SQLAlchemy
┌──────────────────────────────────────────────────▼──────────┐
│              PostgreSQL (farmos DB (shop_ 테이블))                             │
│  categories, products, stores, users, cart_items,           │
│  orders, order_items, reviews, wishlists                    │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

```
[사용자 액션]
    │
    ▼
[React Page/Component] ──→ [Zustand Store] (장바구니 등 클라이언트 상태)
    │
    ▼
[Custom Hook (useProducts 등)] ──→ [TanStack Query]
    │
    ▼
[axios instance (lib/api.ts)] ──→ HTTP Request
    │
    ▼
[FastAPI Router] ──→ [CRUD 함수] ──→ [SQLAlchemy Session] ──→ [PostgreSQL]
    │
    ▼
[Pydantic Response Schema] ──→ JSON Response ──→ [TanStack Query Cache] ──→ [UI 렌더링]
```

### 2.3 Dependencies

| Component | Depends On | Purpose |
|-----------|-----------|---------|
| Pages (React Router) | Components, Hooks | 페이지 조합 |
| Components | types/, lib/utils | UI 렌더링 |
| Custom Hooks | TanStack Query, axios | 서버 상태 관리 |
| Zustand Stores | types/ | 클라이언트 상태 (장바구니) |
| FastAPI Routers | CRUD, Schemas | API 엔드포인트 |
| CRUD | Models, SQLAlchemy Session | DB 조작 |
| Models | SQLAlchemy Base | ORM 매핑 |

---

## 3. Data Model

### 3.1 SQLAlchemy Models (Backend)

```python
# app/models/category.py
class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    icon: Mapped[str | None] = mapped_column(String(50))
    sort_order: Mapped[int] = mapped_column(default=0)

    children: Mapped[list["Category"]] = relationship(back_populates="parent")
    parent: Mapped["Category | None"] = relationship(back_populates="children", remote_side=[id])
    products: Mapped[list["Product"]] = relationship(back_populates="category")


# app/models/store.py
class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(500))
    rating: Mapped[float] = mapped_column(default=0.0)
    product_count: Mapped[int] = mapped_column(default=0)

    products: Mapped[list["Product"]] = relationship(back_populates="store")


# app/models/product.py
class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[int] = mapped_column(nullable=False)           # 원 단위
    discount_rate: Mapped[int] = mapped_column(default=0)        # % 할인율
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id"))
    thumbnail: Mapped[str | None] = mapped_column(String(500))
    images: Mapped[str | None] = mapped_column(Text)             # JSON array
    options: Mapped[str | None] = mapped_column(Text)            # JSON array
    stock: Mapped[int] = mapped_column(default=100)
    rating: Mapped[float] = mapped_column(default=0.0)
    review_count: Mapped[int] = mapped_column(default=0)
    sales_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    category: Mapped["Category | None"] = relationship(back_populates="products")
    store: Mapped["Store | None"] = relationship(back_populates="products")
    reviews: Mapped[list["Review"]] = relationship(back_populates="product")


# app/models/user.py
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    address: Mapped[str | None] = mapped_column(Text)            # JSON
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    cart_items: Mapped[list["CartItem"]] = relationship(back_populates="user")
    orders: Mapped[list["Order"]] = relationship(back_populates="user")
    reviews: Mapped[list["Review"]] = relationship(back_populates="user")
    wishlists: Mapped[list["Wishlist"]] = relationship(back_populates="user")


# app/models/cart.py
class CartItem(Base):
    __tablename__ = "cart_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(default=1)
    selected_option: Mapped[str | None] = mapped_column(Text)    # JSON
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    user: Mapped["User"] = relationship(back_populates="cart_items")
    product: Mapped["Product"] = relationship()


# app/models/order.py
class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    total_price: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    shipping_address: Mapped[str | None] = mapped_column(Text)   # JSON
    payment_method: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    user: Mapped["User"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    price: Mapped[int] = mapped_column(nullable=False)
    selected_option: Mapped[str | None] = mapped_column(Text)    # JSON

    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()


# app/models/review.py
class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    rating: Mapped[int] = mapped_column(nullable=False)          # 1~5
    content: Mapped[str | None] = mapped_column(Text)
    images: Mapped[str | None] = mapped_column(Text)             # JSON array
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    product: Mapped["Product"] = relationship(back_populates="reviews")
    user: Mapped["User"] = relationship(back_populates="reviews")


# app/models/wishlist.py
class Wishlist(Base):
    __tablename__ = "wishlists"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    user: Mapped["User"] = relationship(back_populates="wishlists")
    product: Mapped["Product"] = relationship()

    __table_args__ = (UniqueConstraint("user_id", "product_id"),)
```

### 3.2 Entity Relationships

```
[Category] 1 ──── N [Product]
    │ (self-ref)
    └── parent/children

[Store] 1 ──── N [Product]

[User] 1 ──── N [CartItem] N ──── 1 [Product]
  │
  ├── 1 ──── N [Order] 1 ──── N [OrderItem] N ──── 1 [Product]
  │
  ├── 1 ──── N [Review] N ──── 1 [Product]
  │
  └── 1 ──── N [Wishlist] N ──── 1 [Product]
```

### 3.3 TypeScript Types (Frontend)

```typescript
// types/product.ts
interface Product {
  id: number;
  name: string;
  description: string | null;
  price: number;
  discountRate: number;
  categoryId: number | null;
  storeId: number | null;
  thumbnail: string | null;
  images: string[];
  options: ProductOption[];
  stock: number;
  rating: number;
  reviewCount: number;
  salesCount: number;
  createdAt: string;
  // joined
  category?: Category;
  store?: Store;
}

interface ProductOption {
  name: string;        // e.g., "색상", "사이즈"
  values: string[];    // e.g., ["빨강", "파랑"]
}

interface ProductListResponse {
  items: Product[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

// types/category.ts
interface Category {
  id: number;
  name: string;
  parentId: number | null;
  icon: string | null;
  sortOrder: number;
  children?: Category[];
}

// types/cart.ts
interface CartItem {
  id: number;
  productId: number;
  quantity: number;
  selectedOption: Record<string, string> | null;
  product: Product;
}

// types/order.ts
interface Order {
  id: number;
  totalPrice: number;
  status: "pending" | "paid" | "shipping" | "delivered" | "cancelled";
  shippingAddress: ShippingAddress | null;
  paymentMethod: string | null;
  createdAt: string;
  items: OrderItem[];
}

interface OrderItem {
  id: number;
  productId: number;
  quantity: number;
  price: number;
  selectedOption: Record<string, string> | null;
  product: Product;
}

interface ShippingAddress {
  zipCode: string;
  address: string;
  detail: string;
  recipient: string;
  phone: string;
}

// types/user.ts
interface User {
  id: number;
  name: string;
  email: string;
  phone: string | null;
  address: ShippingAddress | null;
}

// types/store.ts
interface Store {
  id: number;
  name: string;
  description: string | null;
  imageUrl: string | null;
  rating: number;
  productCount: number;
}

// types/review.ts
interface Review {
  id: number;
  productId: number;
  userId: number;
  rating: number;
  content: string | null;
  images: string[];
  createdAt: string;
  user: Pick<User, "id" | "name">;
}
```

---

## 4. API Specification

### 4.1 공통 사항

- **Base URL**: `http://localhost:4000`
- **인증**: `X-User-Id: {userId}` 헤더 (더미, 기본값 1)
- **에러 형식**: `{"detail": "에러 메시지"}`
- **페이지네이션**: `?page=1&limit=20` (기본값)
- **Swagger UI**: `http://localhost:4000/docs`

### 4.2 상품 API

#### `GET /api/products`
상품 목록 조회 (필터/정렬/페이지네이션)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| page | int | 1 | 페이지 번호 |
| limit | int | 20 | 페이지당 개수 |
| category_id | int | - | 카테고리 필터 |
| sort | str | "latest" | 정렬: latest, price_asc, price_desc, popular, rating |
| min_price | int | - | 최소 가격 |
| max_price | int | - | 최대 가격 |

**Response (200):**
```json
{
  "items": [
    {
      "id": 1,
      "name": "유기농 사과 3kg",
      "price": 25000,
      "discountRate": 10,
      "thumbnail": "https://picsum.photos/seed/apple/400/400",
      "rating": 4.5,
      "reviewCount": 12,
      "salesCount": 150,
      "storeName": "행복한 과수원"
    }
  ],
  "total": 45,
  "page": 1,
  "limit": 20,
  "totalPages": 3
}
```

#### `GET /api/products/{id}`
상품 상세 조회

**Response (200):**
```json
{
  "id": 1,
  "name": "유기농 사과 3kg",
  "description": "충북 충주산 유기농 사과...",
  "price": 25000,
  "discountRate": 10,
  "thumbnail": "https://picsum.photos/seed/apple/400/400",
  "images": [
    "https://picsum.photos/seed/apple1/800/800",
    "https://picsum.photos/seed/apple2/800/800"
  ],
  "options": [
    {"name": "중량", "values": ["3kg", "5kg", "10kg"]}
  ],
  "stock": 100,
  "rating": 4.5,
  "reviewCount": 12,
  "salesCount": 150,
  "category": {"id": 1, "name": "과일"},
  "store": {"id": 1, "name": "행복한 과수원", "rating": 4.8},
  "createdAt": "2026-03-15T10:00:00"
}
```

#### `GET /api/products/search?q={keyword}`
상품 검색

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| q | str | (required) | 검색 키워드 |
| page | int | 1 | 페이지 |
| limit | int | 20 | 페이지당 개수 |

### 4.3 카테고리 API

#### `GET /api/categories`
카테고리 목록 (트리 구조)

**Response (200):**
```json
[
  {
    "id": 1,
    "name": "과일",
    "icon": "🍎",
    "children": [
      {"id": 5, "name": "사과", "icon": null, "children": []},
      {"id": 6, "name": "배", "icon": null, "children": []}
    ]
  },
  {
    "id": 2,
    "name": "채소",
    "icon": "🥬",
    "children": [...]
  }
]
```

### 4.4 장바구니 API

#### `GET /api/cart`
장바구니 조회 (Header: `X-User-Id`)

**Response (200):**
```json
{
  "items": [
    {
      "id": 1,
      "productId": 1,
      "quantity": 2,
      "selectedOption": {"중량": "3kg"},
      "product": {
        "id": 1,
        "name": "유기농 사과 3kg",
        "price": 25000,
        "discountRate": 10,
        "thumbnail": "https://picsum.photos/seed/apple/400/400",
        "stock": 100
      }
    }
  ],
  "totalPrice": 45000
}
```

#### `POST /api/cart`
장바구니 추가

**Request:**
```json
{
  "productId": 1,
  "quantity": 2,
  "selectedOption": {"중량": "3kg"}
}
```

#### `PUT /api/cart/{id}`
수량 변경

**Request:**
```json
{"quantity": 3}
```

#### `DELETE /api/cart/{id}`
장바구니 항목 삭제

### 4.5 주문 API

#### `POST /api/orders`
주문 생성

**Request:**
```json
{
  "items": [
    {"productId": 1, "quantity": 2, "selectedOption": {"중량": "3kg"}}
  ],
  "shippingAddress": {
    "zipCode": "12345",
    "address": "서울특별시 강남구 테헤란로 123",
    "detail": "456호",
    "recipient": "홍길동",
    "phone": "010-1234-5678"
  },
  "paymentMethod": "card"
}
```

**Response (201):**
```json
{
  "id": 1,
  "totalPrice": 45000,
  "status": "paid",
  "createdAt": "2026-04-02T12:00:00"
}
```

#### `GET /api/orders`
주문 내역 (Header: `X-User-Id`)

#### `GET /api/orders/{id}`
주문 상세

### 4.6 리뷰 API

#### `GET /api/reviews/product/{productId}`
상품 리뷰 목록

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| page | int | 1 | 페이지 |
| limit | int | 10 | 페이지당 개수 |
| sort | str | "latest" | latest, rating_high, rating_low |

### 4.7 스토어 / 사용자 / 찜 API

#### `GET /api/stores/{id}` — 스토어 정보
#### `GET /api/stores/{id}/products` — 스토어 상품 목록
#### `GET /api/users/me` — 내 정보 (더미 사용자 ID=1)
#### `GET /api/wishlists` — 찜 목록
#### `POST /api/wishlists/{productId}` — 찜 토글 (추가/제거)

---

## 5. UI/UX Design

### 5.1 공통 레이아웃

```
┌────────────────────────────────────────────────────────────┐
│  [로고]  [검색바 ─────────────────── 🔍]  [장바구니] [마이] │  ← Header
├────────────────────────────────────────────────────────────┤
│  [전체카테고리▼] [과일] [채소] [축산] [수산] [가공]        │  ← CategoryNav
├────────────────────────────────────────────────────────────┤
│                                                            │
│                    Main Content                            │
│                                                            │
├────────────────────────────────────────────────────────────┤
│  [고객센터] [이용약관] [개인정보] [사업자정보]              │  ← Footer
└────────────────────────────────────────────────────────────┘
```

### 5.2 주요 페이지 와이어프레임

#### 메인 페이지 (`/`)
```
┌────────────────────────────────────────────┐
│           [배너 슬라이더 (자동)]            │
│    ◀  이미지/프로모션 배너 (3~5장)  ▶      │
├────────────────────────────────────────────┤
│  🍎과일  🥬채소  🥩축산  🐟수산           │  ← 카테고리 아이콘
├────────────────────────────────────────────┤
│  ✨ 오늘의 추천 상품                       │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐     │
│  │[img] │ │[img] │ │[img] │ │[img] │     │
│  │상품명│ │상품명│ │상품명│ │상품명│     │
│  │가격  │ │가격  │ │가격  │ │가격  │     │
│  │⭐4.5 │ │⭐4.2 │ │⭐4.8 │ │⭐4.0 │     │
│  └──────┘ └──────┘ └──────┘ └──────┘     │
├────────────────────────────────────────────┤
│  🔥 인기 상품 TOP 10                      │
│  (횡스크롤 상품 카드 리스트)               │
├────────────────────────────────────────────┤
│  🆕 신상품                                │
│  (그리드 4열 상품 카드)                    │
└────────────────────────────────────────────┘
```

#### 상품 상세 페이지 (`/products/[id]`)
```
┌─────────────────────┬──────────────────────┐
│                     │  [스토어명]           │
│   [이미지 갤러리]   │  상품명              │
│   메인 이미지       │  ⭐4.5 (리뷰 12개)   │
│                     │                      │
│  [썸네일1][2][3][4] │  25,000원 → 22,500원 │
│                     │  10% 할인            │
│                     │                      │
│                     │  옵션 선택:          │
│                     │  [중량 ▼] 3kg        │
│                     │  [수량 -  1  +]      │
│                     │                      │
│                     │  [장바구니] [바로구매]│
├─────────────────────┴──────────────────────┤
│  [상품정보] [리뷰(12)] [문의] [배송]       │  ← 탭
├────────────────────────────────────────────┤
│  상세 설명 영역...                         │
│  (HTML 렌더링 또는 이미지)                 │
├────────────────────────────────────────────┤
│  리뷰 영역                                │
│  ┌─────────────────────────────────────┐  │
│  │ ⭐⭐⭐⭐⭐ 홍길동 | 2026.03.20     │  │
│  │ 사과가 정말 맛있어요!              │  │
│  │ [리뷰 이미지]                      │  │
│  └─────────────────────────────────────┘  │
└────────────────────────────────────────────┘
```

#### 장바구니 (`/cart`)
```
┌────────────────────────────────────────────────────────────┐
│  장바구니 (2개 상품)                                       │
├────────────────────────────────────┬───────────────────────┤
│  [☑] 전체선택 (2/2)  [선택삭제]   │                       │
├────────────────────────────────────┤   주문 요약           │
│  [☑] [img] 유기농 사과 3kg        │   상품금액: 45,000원  │
│       22,500원 × 2  = 45,000원    │   배송비:   무료      │
│       옵션: 3kg                   │   ─────────────────   │
│       [- 2 +]           [삭제]    │   총 금액: 45,000원   │
├────────────────────────────────────┤                       │
│  [☑] [img] 한우 등심 1kg          │   [주문하기 (2)]      │
│       55,000원 × 1  = 55,000원    │                       │
│       [- 1 +]           [삭제]    │                       │
├────────────────────────────────────┤                       │
│                                    │                       │
└────────────────────────────────────┴───────────────────────┘
```

### 5.3 User Flow

```
[메인] ──→ [카테고리 클릭] ──→ [상품 목록] ──→ [상품 상세]
                                                    │
                               [검색] ──→ [검색 결과] ──→ [상품 상세]
                                                    │
                                              ┌─────┴──────┐
                                              ▼            ▼
                                         [장바구니]   [바로구매]
                                              │            │
                                              └─────┬──────┘
                                                    ▼
                                              [주문서 작성]
                                                    │
                                                    ▼
                                              [주문 완료]
                                                    │
                                                    ▼
                                         [마이페이지/주문내역]
```

### 5.4 Component List

| Component | Location | Responsibility |
|-----------|----------|----------------|
| **Header** | `components/common/Header.tsx` | 로고, 검색바, 장바구니/마이 링크 |
| **Footer** | `components/common/Footer.tsx` | 하단 링크, 사업자 정보 |
| **SearchBar** | `components/common/SearchBar.tsx` | 검색 입력, 자동완성 |
| **CategoryNav** | `components/common/CategoryNav.tsx` | 카테고리 탑 네비게이션 |
| **ProductCard** | `components/product/ProductCard.tsx` | 상품 카드 (목록용) |
| **ProductGrid** | `components/product/ProductGrid.tsx` | 상품 그리드 레이아웃 |
| **ImageGallery** | `components/product/ImageGallery.tsx` | 상품 이미지 갤러리 |
| **OptionSelector** | `components/product/OptionSelector.tsx` | 상품 옵션/수량 선택 |
| **Banner** | `components/home/Banner.tsx` | 메인 배너 슬라이더 |
| **RecommendSection** | `components/home/RecommendSection.tsx` | 추천 상품 섹션 |
| **PopularSection** | `components/home/PopularSection.tsx` | 인기 상품 섹션 |
| **CartItem** | `components/cart/CartItem.tsx` | 장바구니 항목 |
| **CartSummary** | `components/cart/CartSummary.tsx` | 주문 요약, 총 금액 |
| **OrderForm** | `components/order/OrderForm.tsx` | 배송지/결제 입력 |
| **PaymentSelector** | `components/order/PaymentSelector.tsx` | 결제 수단 선택 |
| **ReviewList** | `components/review/ReviewList.tsx` | 리뷰 목록 |
| **StarRating** | `components/review/StarRating.tsx` | 별점 표시 |
| **Pagination** | `components/common/Pagination.tsx` | 페이지네이션 |
| **QuantitySelector** | `components/common/QuantitySelector.tsx` | 수량 +/- 버튼 |

---

## 6. State Management

### 6.1 Zustand Stores (Client State)

```typescript
// stores/cartStore.ts
interface CartStore {
  items: CartItem[];
  addItem: (product: Product, quantity: number, option?: Record<string, string>) => void;
  removeItem: (cartItemId: number) => void;
  updateQuantity: (cartItemId: number, quantity: number) => void;
  clearCart: () => void;
  selectedIds: Set<number>;
  toggleSelect: (cartItemId: number) => void;
  selectAll: () => void;
  deselectAll: () => void;
  totalPrice: () => number;
  selectedTotalPrice: () => number;
}

// stores/userStore.ts
interface UserStore {
  user: User | null;          // 더미 사용자 (ID=1)
  isLoggedIn: boolean;
  setUser: (user: User) => void;
}

// stores/searchStore.ts
interface SearchStore {
  keyword: string;
  recentSearches: string[];
  setKeyword: (keyword: string) => void;
  addRecentSearch: (keyword: string) => void;
  clearRecentSearches: () => void;
}
```

### 6.2 TanStack Query Keys

```typescript
// 쿼리 키 컨벤션
const queryKeys = {
  products: {
    all: ["products"] as const,
    list: (filters: ProductFilters) => ["products", "list", filters] as const,
    detail: (id: number) => ["products", "detail", id] as const,
    search: (keyword: string) => ["products", "search", keyword] as const,
  },
  categories: {
    all: ["categories"] as const,
  },
  cart: {
    all: ["cart"] as const,
  },
  orders: {
    all: ["orders"] as const,
    detail: (id: number) => ["orders", "detail", id] as const,
  },
  reviews: {
    byProduct: (productId: number) => ["reviews", "product", productId] as const,
  },
  stores: {
    detail: (id: number) => ["stores", "detail", id] as const,
    products: (id: number) => ["stores", "products", id] as const,
  },
  wishlists: {
    all: ["wishlists"] as const,
  },
};
```

---

## 7. Error Handling

### 7.1 Backend (FastAPI)

```python
# 공통 에러 응답
class ErrorResponse(BaseModel):
    detail: str

# HTTP 예외
raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다")
raise HTTPException(status_code=400, detail="유효하지 않은 수량입니다")
```

### 7.2 Frontend (TanStack Query)

```typescript
// lib/api.ts
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:4000",
  headers: { "X-User-Id": "1" },  // 더미 인증
});

// 글로벌 에러 핸들러는 QueryClient defaultOptions에서 처리
// 404: "상품을 찾을 수 없습니다" 토스트
// 500: "서버 오류가 발생했습니다" 토스트
```

---

## 8. Security Considerations

- [x] CORS 설정: Frontend origin만 허용 (`http://localhost:5174`)
- [ ] Input validation: Pydantic 스키마로 자동 검증 (FastAPI)
- [x] SQL Injection 방지: SQLAlchemy ORM 사용 (parameterized queries)
- [ ] XSS 방지: React 기본 이스케이핑 + dangerouslySetInnerHTML 미사용
- [-] 인증: 더미 (`X-User-Id` 헤더) — 실제 서비스에서는 JWT로 교체

---

## 9. Backend Project Configuration

### 9.1 pyproject.toml

```toml
[project]
name = "shopping-mall-backend"
version = "0.1.0"
description = "Shopping Mall Dummy API Server (FastAPI + PostgreSQL)"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "sqlalchemy>=2.0.36",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.7.0",
    "python-dotenv>=1.0.1",
]

[tool.uv]
exclude-newer = "7 days"
```

### 9.2 database.py

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = "postgresql+psycopg2://postgres:root@localhost:5432/farmos"

engine = create_engine(
    DATABASE_URL,
    connect_args={"pool_pre_ping": False},  # PostgreSQL 멀티스레드 허용
    echo=False,
)
SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### 9.3 main.py (FastAPI App)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import products, categories, cart, orders, users, reviews, stores, wishlists

app = FastAPI(title="Shopping Mall API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(categories.router, prefix="/api/categories", tags=["Categories"])
app.include_router(cart.router, prefix="/api/cart", tags=["Cart"])
app.include_router(orders.router, prefix="/api/orders", tags=["Orders"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(reviews.router, prefix="/api/reviews", tags=["Reviews"])
app.include_router(stores.router, prefix="/api/stores", tags=["Stores"])
app.include_router(wishlists.router, prefix="/api/wishlists", tags=["Wishlists"])
```

---

## 10. Coding Convention Reference

### 10.1 Naming Conventions

| Target | Frontend (TS) | Backend (Python) |
|--------|--------------|-----------------|
| Components | PascalCase (`ProductCard`) | N/A |
| Functions/Hooks | camelCase (`useProducts`) | snake_case (`get_products`) |
| Constants | UPPER_SNAKE | UPPER_SNAKE |
| Types/Interfaces | PascalCase (`Product`) | PascalCase (`ProductSchema`) |
| Files (component) | PascalCase.tsx | snake_case.py |
| Files (utility) | camelCase.ts | snake_case.py |
| Folders | kebab-case | snake_case |
| DB columns | N/A | snake_case |
| API response fields | camelCase (JSON) | camelCase (alias from snake_case) |

### 10.2 Pydantic alias 전략

```python
class ProductSchema(BaseModel):
    id: int
    name: str
    discount_rate: int  # Python snake_case

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,   # JSON은 camelCase로 출력
        populate_by_name=True,
    )
```

---

## 11. Implementation Order

### Phase 1: Backend 기반 (Day 1-2)

1. [ ] `shopping_mall/backend/` 프로젝트 초기화
   - pyproject.toml, .python-version, .env, .gitignore
   - `uv venv && uv sync`
2. [ ] `app/database.py` — SQLAlchemy + PostgreSQL 연결
3. [ ] `app/models/` — 전체 모델 정의 (9개 테이블)
4. [ ] `app/schemas/` — Pydantic 스키마 정의
5. [ ] `bootstrap/shoppingmall.py` — 시드 데이터 스크립트 (40+ 상품 등)
6. [ ] `app/main.py` — FastAPI 앱 + CORS 설정
7. [ ] `app/routers/products.py` — 상품 목록/상세/검색 API
8. [ ] `app/routers/categories.py` — 카테고리 API
9. [ ] Swagger UI 동작 확인

### Phase 2: Frontend 기반 (Day 3-4)

10. [ ] `shopping_mall/frontend/` React+Vite 초기화
    - `npm create vite@latest . -- --template react-ts` + Tailwind + React Router
    - package.json, tsconfig.json, vite.config.ts
11. [ ] `src/lib/api.ts` — axios 인스턴스
12. [ ] `src/types/` — 전체 TypeScript 타입 정의
13. [ ] `src/components/common/` — Header, Footer, CategoryNav, SearchBar
14. [ ] `src/App.tsx` + `src/router.tsx` — 공통 레이아웃 + 라우터 설정
15. [ ] `src/pages/HomePage.tsx` — 메인 페이지 (배너, 추천, 인기)
16. [ ] `src/hooks/useProducts.ts` — 상품 관련 쿼리 훅
17. [ ] `src/pages/ProductListPage.tsx` — 상품 목록
18. [ ] `src/pages/ProductDetailPage.tsx` — 상품 상세

### Phase 3: 쇼핑 플로우 (Day 5-6)

19. [ ] `app/routers/cart.py` — 장바구니 API (Backend)
20. [ ] `app/routers/orders.py` — 주문 API (Backend)
21. [ ] `src/stores/cartStore.ts` — Zustand 장바구니 스토어
22. [ ] `src/pages/CartPage.tsx` — 장바구니 UI
23. [ ] `src/pages/OrderPage.tsx` — 주문서 작성
24. [ ] `src/pages/OrderCompletePage.tsx` — 주문 완료

### Phase 4: 부가 기능 (Day 7-8)

25. [ ] `src/pages/SearchPage.tsx` — 검색 결과
26. [ ] `src/components/common/SearchBar.tsx` — 자동완성
27. [ ] `src/pages/MyPage.tsx`, `src/pages/MyOrdersPage.tsx`, `src/pages/WishlistPage.tsx` — 마이페이지 (주문내역, 찜)
28. [ ] `app/routers/reviews.py` — 리뷰 API (Backend)
29. [ ] `app/routers/stores.py` — 스토어 API (Backend)
30. [ ] `src/pages/StorePage.tsx` — 판매자 스토어
31. [ ] `src/components/review/` — 리뷰 컴포넌트
32. [ ] 반응형 CSS 최종 점검

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-04-02 | Initial design (FastAPI + PostgreSQL + React+Vite) | clover0309 |
| 0.2 | 2026-04-02 | Stack change: Next.js → React+Vite, FarmOS 프론트엔드 스택 통일 | clover0309 |

