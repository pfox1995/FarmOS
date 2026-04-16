#!/usr/bin/env python
# ruff: noqa: E402
# pyright: reportMissingImports=false, reportMissingModuleSource=false
"""ShoppingMall DB 시드 로직.

실행 예시:
  uv run python ../../bootstrap/shoppingmall_seed.py

담당 범위:
1) 스키마 초기화(drop/create)
2) 기본 쇼핑몰 데이터 시드
3) 백오피스 데이터 시드
4) 초기 리뷰 샘플(30건) 시드
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from _bootstrap_common import (  # type: ignore[import-not-found]
    error,
    info,
    set_log_prefix,
)

# 실행 위치와 무관하게 shopping_mall/backend를 import 루트로 맞춘다.
ROOT = Path(__file__).resolve().parents[1]
SHOP_BACKEND_DIR = ROOT / "shopping_mall" / "backend"
if str(SHOP_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(SHOP_BACKEND_DIR))

from app.database import Base, SessionLocal, engine
from app.models import (
    CartItem,
    Category,
    ChatLog,
    CustomerSegment,
    ExpenseEntry,
    HarvestSchedule,
    Order,
    OrderItem,
    Product,
    RevenueEntry,
    Review,
    Shipment,
    Store,
    User,
    WeeklyReport,
    Wishlist,
)

# =========================
# 수정이 쉬운 상단 설정값
# =========================

EXPECTED_ROW_COUNTS = {
    "shop_categories": 12,
    "shop_stores": 5,
    "shop_products": 42,
    "shop_users": 5,
    "shop_reviews": 30,
    "shop_orders": 10,
    "shop_order_items": 19,
    "shop_cart_items": 5,
    "shop_wishlists": 8,
    "shop_shipments": 5,
    "shop_harvest_schedules": 8,
    "shop_revenue_entries": 15,
    "shop_expense_entries": 10,
    "shop_weekly_reports": 2,
    "shop_customer_segments": 5,
    "shop_chat_logs": 5,
}
LOG_PREFIX = "SHOP-SEED"


# shop_categories 구성 정보
PARENT_CATEGORIES = [
    (1, "과일", "apple", 1),
    (2, "채소", "carrot", 2),
    (3, "축산", "meat", 3),
    (4, "수산", "fish", 4),
]
CHILD_CATEGORIES = [
    (5, "사과/배", 1, 1),
    (6, "감귤/오렌지", 1, 2),
    (7, "엽채류", 2, 1),
    (8, "근채류", 2, 2),
    (9, "소고기", 3, 1),
    (10, "돼지고기", 3, 2),
    (11, "생선", 4, 1),
    (12, "해산물", 4, 2),
]

STORES = [
    (1, "행복한 과수원", "신선한 과일을 산지에서 직접 배송합니다.", 4.8, 10),
    (2, "신선한 채소밭", "무농약 유기농 채소를 재배합니다.", 4.6, 10),
    (3, "한우마을", "1++ 등급 한우 전문 농장입니다.", 4.9, 8),
    (4, "바다의선물", "당일 경매 신선한 수산물을 직송합니다.", 4.7, 8),
    (5, "농부의정성", "정성 가득 유기농 농산물 전문점입니다.", 4.5, 6),
]

# 42개 상품명. 수정 편의를 위해 상단 상수로 고정한다.
PRODUCT_NAMES = [
    "경북 부사 사과 5kg",
    "충남 신고배 7.5kg",
    "청송 꿀사과 3kg",
    "나주배 선물세트 5kg",
    "홍로사과 2kg",
    "제주 감귤 5kg",
    "제주 한라봉 3kg",
    "카라카라 오렌지 2kg",
    "천혜향 2kg",
    "레드향 3kg",
    "유기농 상추 300g",
    "깻잎 100매",
    "시금치 500g",
    "배추 1포기",
    "청경채 200g",
    "감자 3kg",
    "고구마 3kg",
    "당근 1kg",
    "양파 3kg",
    "무 1개",
    "한우 등심 1++ 300g",
    "한우 갈비살 500g",
    "한우 채끝 200g",
    "한우 불고기용 300g",
    "한우 사골 2kg",
    "제주 흑돼지 삼겹살 500g",
    "목살 구이용 500g",
    "돼지갈비 양념 1kg",
    "노르웨이 생연어 300g",
    "제주 광어회 500g",
    "고등어 2마리",
    "참치회 400g",
    "갈치 2마리",
    "통영 생굴 1kg",
    "킹크랩 1마리 (1.5kg)",
    "새우 (대) 1kg",
    "전복 10마리",
    "오징어 3마리",
    "유기농 블루베리 500g",
    "친환경 방울토마토 1kg",
    "유기농 브로콜리 2개",
    "흙당근 2kg",
]

# 상품별 카테고리/스토어 매핑(1-based product id)
PRODUCT_CATEGORY_BY_ID = [
    5,
    5,
    5,
    5,
    5,
    6,
    6,
    6,
    6,
    6,
    7,
    7,
    7,
    7,
    7,
    8,
    8,
    8,
    8,
    8,
    9,
    9,
    9,
    9,
    9,
    10,
    10,
    10,
    11,
    11,
    11,
    11,
    11,
    12,
    12,
    12,
    12,
    12,
    6,
    7,
    7,
    8,
]
PRODUCT_STORE_BY_ID = [
    1,
    1,
    1,
    5,
    1,
    1,
    1,
    5,
    1,
    5,
    2,
    2,
    2,
    2,
    5,
    2,
    2,
    2,
    5,
    2,
    3,
    3,
    3,
    3,
    3,
    3,
    3,
    3,
    4,
    4,
    4,
    4,
    4,
    4,
    4,
    4,
    4,
    4,
    5,
    5,
    5,
    5,
]

SHOP_USERS = [
    (
        1,
        "김민수",
        "minsu@example.com",
        "010-1234-5678",
        {
            "zipcode": "06234",
            "address": "서울시 강남구 역삼동 123-45",
            "detail": "아파트 101동 202호",
        },
    ),
    (
        2,
        "이지은",
        "jieun@example.com",
        "010-2345-6789",
        {
            "zipcode": "04523",
            "address": "서울시 중구 명동 67-8",
            "detail": "오피스텔 301호",
        },
    ),
    (
        3,
        "박준혁",
        "junhyuk@example.com",
        "010-3456-7890",
        {
            "zipcode": "13487",
            "address": "경기도 성남시 분당구 정자동 45-6",
            "detail": "",
        },
    ),
    (
        4,
        "최수연",
        "sooyeon@example.com",
        "010-4567-8901",
        {
            "zipcode": "48058",
            "address": "부산시 해운대구 우동 789-10",
            "detail": "빌라 2층",
        },
    ),
    (
        5,
        "정하늘",
        "haneul@example.com",
        "010-5678-9012",
        {"zipcode": "61452", "address": "광주시 동구 충장로 12-3", "detail": "주택"},
    ),
]


@dataclass
class SeedState:
    now: datetime
    products: list[Product]
    users: list[User]
    orders: list[Order]


def _product_price(pid: int) -> int:
    # 42개 상품에 대해 안정적인 가격 분포를 부여한다.
    base = [3200, 5500, 8900, 12000, 18900, 24000, 32000, 45000, 52000]
    return base[(pid - 1) % len(base)]


def _product_discount(pid: int) -> int:
    values = [0, 5, 10, 15, 20]
    return values[(pid - 1) % len(values)]


def seed_core_data(db) -> SeedState:
    now = datetime.now(timezone.utc)

    db.add_all(
        Category(id=cid, name=name, icon=icon, sort_order=sort)
        for cid, name, icon, sort in PARENT_CATEGORIES
    )
    db.add_all(
        Category(id=cid, name=name, parent_id=parent, sort_order=sort)
        for cid, name, parent, sort in CHILD_CATEGORIES
    )

    db.add_all(
        Store(
            id=sid,
            name=name,
            description=desc,
            image_url=f"https://picsum.photos/seed/store{sid}/200/200",
            rating=rating,
            product_count=pc,
        )
        for sid, name, desc, rating, pc in STORES
    )
    db.flush()

    products: list[Product] = []
    for i, name in enumerate(PRODUCT_NAMES, start=1):
        category_id = PRODUCT_CATEGORY_BY_ID[i - 1]
        store_id = PRODUCT_STORE_BY_ID[i - 1]
        price = _product_price(i)
        discount = _product_discount(i)
        product = Product(
            id=i,
            name=name,
            description=f"{name} 상품 설명",
            price=price,
            discount_rate=discount,
            category_id=category_id,
            store_id=store_id,
            stock=80 + ((i * 7) % 140),
            rating=round(4.2 + (i % 7) * 0.1, 1),
            review_count=10 + (i % 90),
            sales_count=50 + (i * 9),
            thumbnail=f"https://picsum.photos/seed/product{i}/400/400",
            images=json.dumps(
                [
                    f"https://picsum.photos/seed/product{i}a/600/600",
                    f"https://picsum.photos/seed/product{i}b/600/600",
                    f"https://picsum.photos/seed/product{i}c/600/600",
                ]
            ),
            options=json.dumps(["기본"]),
            created_at=now - timedelta(days=42 - i),
        )
        products.append(product)
    db.add_all(products)
    db.flush()

    users = [
        User(
            id=uid,
            name=name,
            email=email,
            phone=phone,
            address=json.dumps(address, ensure_ascii=False),
        )
        for uid, name, email, phone, address in SHOP_USERS
    ]
    db.add_all(users)
    db.flush()

    # 초기 30건 리뷰 샘플 (최종 1000건 재시드는 bootstrap/shoppingmall_review_seed.py에서 수행)
    reviews = []
    for i in range(30):
        reviews.append(
            Review(
                id=i + 1,
                product_id=(i % 42) + 1,
                user_id=(i % 5) + 1,
                rating=round(3.5 + (i % 4) * 0.4, 1),
                content=f"{PRODUCT_NAMES[i % 42]} 후기 #{i + 1}",
                images=json.dumps([f"https://picsum.photos/seed/review{i + 1}/300/300"])
                if i % 3 == 0
                else None,
                created_at=now - timedelta(days=30 - i, hours=i),
            )
        )
    db.add_all(reviews)
    db.flush()

    statuses = [
        "pending",
        "paid",
        "shipping",
        "delivered",
        "delivered",
        "paid",
        "shipping",
        "delivered",
        "cancelled",
        "delivered",
    ]
    orders: list[Order] = []
    for i in range(10):
        orders.append(
            Order(
                id=i + 1,
                user_id=(i % 5) + 1,
                total_price=0,
                status=statuses[i],
                shipping_address=json.dumps(
                    {
                        "zipcode": "06234",
                        "address": "서울시 강남구 역삼동",
                        "detail": f"테스트 {i + 1}호",
                    },
                    ensure_ascii=False,
                ),
                payment_method="card" if i % 2 == 0 else "bank_transfer",
                created_at=now - timedelta(days=20 - i * 2),
            )
        )
    db.add_all(orders)
    db.flush()

    order_items = []
    total_prices = [0] * 10
    for i in range(10):
        for j in range((i % 3) + 1):
            pid = (i * 3 + j) % 42 + 1
            prod = products[pid - 1]
            discounted = prod.price * (100 - prod.discount_rate) // 100
            qty = (j % 3) + 1
            item_price = discounted * qty
            total_prices[i] += item_price
            order_items.append(
                OrderItem(
                    order_id=i + 1,
                    product_id=pid,
                    quantity=qty,
                    price=item_price,
                    selected_option=json.dumps("기본"),
                )
            )
    db.add_all(order_items)
    db.flush()
    for i, order in enumerate(orders):
        order.total_price = total_prices[i]
    db.flush()

    db.add_all(
        [
            CartItem(
                user_id=1, product_id=1, quantity=2, selected_option=json.dumps("기본")
            ),
            CartItem(
                user_id=1, product_id=6, quantity=1, selected_option=json.dumps("기본")
            ),
            CartItem(
                user_id=1, product_id=21, quantity=1, selected_option=json.dumps("기본")
            ),
            CartItem(
                user_id=2, product_id=3, quantity=3, selected_option=json.dumps("기본")
            ),
            CartItem(
                user_id=2, product_id=17, quantity=1, selected_option=json.dumps("기본")
            ),
        ]
    )

    db.add_all(
        [
            Wishlist(user_id=1, product_id=1),
            Wishlist(user_id=1, product_id=7),
            Wishlist(user_id=1, product_id=21),
            Wishlist(user_id=1, product_id=34),
            Wishlist(user_id=2, product_id=3),
            Wishlist(user_id=2, product_id=26),
            Wishlist(user_id=3, product_id=9),
            Wishlist(user_id=3, product_id=29),
        ]
    )
    db.flush()
    return SeedState(now=now, products=products, users=users, orders=orders)


def seed_backoffice_data(db, state: SeedState) -> None:
    now = state.now

    db.add_all(
        [
            Shipment(
                order_id=2,
                carrier="CJ대한통운",
                tracking_number="6300123456789",
                status="delivered",
                delivered_at=now - timedelta(days=5),
                tracking_history=json.dumps(
                    [
                        {
                            "from": "registered",
                            "to": "picked_up",
                            "timestamp": (now - timedelta(days=8)).isoformat(),
                        },
                        {
                            "from": "picked_up",
                            "to": "in_transit",
                            "timestamp": (now - timedelta(days=7)).isoformat(),
                        },
                        {
                            "from": "in_transit",
                            "to": "delivered",
                            "timestamp": (now - timedelta(days=5)).isoformat(),
                        },
                    ],
                    ensure_ascii=False,
                ),
                created_at=now - timedelta(days=9),
            ),
            Shipment(
                order_id=3,
                carrier="한진택배",
                tracking_number="4200987654321",
                status="in_transit",
                created_at=now - timedelta(days=3),
            ),
            Shipment(
                order_id=6,
                carrier="로젠택배",
                tracking_number="9100555666777",
                status="picked_up",
                created_at=now - timedelta(days=1),
            ),
            Shipment(
                order_id=7,
                carrier="CJ대한통운",
                tracking_number="6300222333444",
                status="registered",
                created_at=now - timedelta(hours=6),
            ),
            Shipment(
                order_id=8,
                carrier="우체국택배",
                tracking_number="1300111222333",
                status="delivered",
                delivered_at=now - timedelta(days=10),
                created_at=now - timedelta(days=14),
            ),
        ]
    )

    db.add_all(
        [
            HarvestSchedule(
                product_id=1,
                harvest_date="2026-04-05",
                estimated_quantity=500,
                actual_quantity=480,
                status="harvested",
            ),
            HarvestSchedule(
                product_id=3,
                harvest_date="2026-04-08",
                estimated_quantity=300,
                status="planned",
            ),
            HarvestSchedule(
                product_id=6,
                harvest_date="2026-04-03",
                estimated_quantity=1000,
                actual_quantity=1050,
                status="shipped",
            ),
            HarvestSchedule(
                product_id=7,
                harvest_date="2026-04-10",
                estimated_quantity=600,
                status="planned",
            ),
            HarvestSchedule(
                product_id=11,
                harvest_date="2026-04-02",
                estimated_quantity=200,
                actual_quantity=190,
                status="harvested",
            ),
            HarvestSchedule(
                product_id=16,
                harvest_date="2026-04-15",
                estimated_quantity=800,
                status="planned",
            ),
            HarvestSchedule(
                product_id=21,
                harvest_date="2026-04-12",
                estimated_quantity=100,
                status="planned",
            ),
            HarvestSchedule(
                product_id=26,
                harvest_date="2026-04-20",
                estimated_quantity=400,
                status="planned",
            ),
        ]
    )

    paid_like = [
        o for o in state.orders if o.status in {"paid", "shipping", "delivered"}
    ]
    for order in paid_like:
        order_items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
        for item in order_items:
            db.add(
                RevenueEntry(
                    date=order.created_at.strftime("%Y-%m-%d")
                    if order.created_at
                    else "2026-03-15",
                    order_id=order.id,
                    product_id=item.product_id,
                    quantity=item.quantity,
                    unit_price=item.price // item.quantity
                    if item.quantity
                    else item.price,
                    total_amount=item.price,
                    category="sales",
                )
            )

    db.add_all(
        [
            ExpenseEntry(
                date="2026-03-15",
                description="택배 박스 500개 구매",
                amount=150000,
                category="packaging",
            ),
            ExpenseEntry(
                date="2026-03-16",
                description="CJ대한통운 택배비 월정산",
                amount=320000,
                category="shipping",
            ),
            ExpenseEntry(
                date="2026-03-18",
                description="유기농 비료 20kg",
                amount=85000,
                category="material",
            ),
            ExpenseEntry(
                date="2026-03-20",
                description="포장 아르바이트 3명 일당",
                amount=270000,
                category="labor",
            ),
            ExpenseEntry(
                date="2026-03-22",
                description="온실 전기요금",
                amount=180000,
                category="utility",
            ),
            ExpenseEntry(
                date="2026-03-25",
                description="인스타그램 광고비",
                amount=200000,
                category="marketing",
            ),
            ExpenseEntry(
                date="2026-03-27",
                description="아이스팩 1000개",
                amount=120000,
                category="packaging",
            ),
            ExpenseEntry(
                date="2026-03-28",
                description="종자 구입 (토마토, 상추)",
                amount=95000,
                category="material",
            ),
            ExpenseEntry(
                date="2026-03-30",
                description="배송차량 유류비",
                amount=150000,
                category="shipping",
            ),
            ExpenseEntry(
                date="2026-04-01",
                description="사무실 인터넷 요금",
                amount=55000,
                category="utility",
            ),
        ]
    )

    db.add_all(
        [
            WeeklyReport(
                week_start="2026-03-16",
                week_end="2026-03-22",
                total_revenue=1250000,
                total_expense=825000,
                net_profit=425000,
                report_content=(
                    "[주간 리포트 2026-03-16 ~ 2026-03-22]\n"
                    "총 매출 1,250,000원으로 전주 대비 12% 증가했습니다.\n"
                    "한우 등심과 제주 감귤이 인기 상품 1, 2위를 차지했습니다.\n"
                    "포장비와 인건비가 전체 비용의 50%를 차지하여 효율화가 필요합니다.\n"
                    "다음 주 봄 시즌 프로모션 준비를 권장합니다."
                ),
                generated_at=now - timedelta(days=10),
            ),
            WeeklyReport(
                week_start="2026-03-23",
                week_end="2026-03-29",
                total_revenue=1480000,
                total_expense=745000,
                net_profit=735000,
                report_content=(
                    "[주간 리포트 2026-03-23 ~ 2026-03-29]\n"
                    "매출이 전주 대비 18% 증가하여 좋은 성장세를 보이고 있습니다.\n"
                    "청송 꿀사과와 통영 생굴의 판매가 급증했습니다.\n"
                    "택배비 비율이 감소하여 비용 효율이 개선되었습니다.\n"
                    "4월 봄나물 시즌에 맞춘 기획전을 추천합니다."
                ),
                generated_at=now - timedelta(days=3),
            ),
        ]
    )

    for user_id, segment, recency, freq, monetary in [
        (1, "repeat", 5, 2, 120000),
        (2, "loyal", 10, 3, 280000),
        (3, "new", 15, 1, 52000),
        (4, "vip", 3, 5, 650000),
        (5, "at_risk", 75, 2, 95000),
    ]:
        db.add(
            CustomerSegment(
                user_id=user_id,
                segment=segment,
                recency_days=recency,
                frequency=freq,
                monetary=monetary,
                last_updated=now,
            )
        )

    db.add_all(
        [
            ChatLog(
                user_id=1,
                intent="delivery",
                question="제 주문 배송 어디까지 왔나요?",
                answer="주문#2: CJ대한통운 6300123456789 (상태: delivered) - 배송이 완료되었습니다.",
                escalated=False,
                rating=5,
                created_at=now - timedelta(days=5),
            ),
            ChatLog(
                user_id=2,
                intent="storage",
                question="사과 보관 방법이 궁금해요",
                answer="사과는 비닐봉지에 넣어 냉장 보관하세요. 에틸렌 가스를 많이 배출하므로 다른 과일과 분리 보관이 좋습니다.",
                escalated=False,
                rating=4,
                created_at=now - timedelta(days=4),
            ),
            ChatLog(
                user_id=3,
                intent="exchange",
                question="어제 받은 고구마가 상한 것 같아요. 교환 가능한가요?",
                answer="상품 하자 시 수령 후 24시간 이내에 사진과 함께 고객센터로 연락해 주세요. 확인 후 교환 또는 환불 처리해 드리겠습니다.",
                escalated=False,
                rating=3,
                created_at=now - timedelta(days=3),
            ),
            ChatLog(
                user_id=None,
                intent="other",
                question="농장 견학 프로그램이 있나요?",
                answer="해당 문의는 상담원 연결이 필요합니다. 고객센터(1588-0000)로 전화해 주시거나, 잠시만 기다려 주시면 상담원이 연결됩니다.",
                escalated=True,
                rating=None,
                created_at=now - timedelta(days=2),
            ),
            ChatLog(
                user_id=4,
                intent="season",
                question="지금 제철인 과일이 뭐가 있나요?",
                answer="봄철(3-5월)에는 딸기가 가장 인기 있으며, 4월부터는 참외도 출하됩니다. 감귤류(한라봉, 천혜향)도 아직 맛있게 드실 수 있습니다.",
                escalated=False,
                rating=5,
                created_at=now - timedelta(days=1),
            ),
        ]
    )


def print_summary(db) -> None:
    info("ShoppingMall 시드 요약")
    table_model_pairs = [
        ("shop_categories", Category),
        ("shop_stores", Store),
        ("shop_products", Product),
        ("shop_users", User),
        ("shop_reviews", Review),
        ("shop_orders", Order),
        ("shop_order_items", OrderItem),
        ("shop_cart_items", CartItem),
        ("shop_wishlists", Wishlist),
        ("shop_shipments", Shipment),
        ("shop_harvest_schedules", HarvestSchedule),
        ("shop_revenue_entries", RevenueEntry),
        ("shop_expense_entries", ExpenseEntry),
        ("shop_weekly_reports", WeeklyReport),
        ("shop_customer_segments", CustomerSegment),
        ("shop_chat_logs", ChatLog),
    ]
    for table, model in table_model_pairs:
        actual = db.query(model).count()
        expected = EXPECTED_ROW_COUNTS.get(table)
        suffix = f" (expected {expected})" if expected is not None else ""
        print(f"  - {table}: {actual}{suffix}")


def main() -> int:
    set_log_prefix(LOG_PREFIX)
    info("ShoppingMall 스키마 초기화 시작")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        state = seed_core_data(db)
        seed_backoffice_data(db, state)
        db.commit()
        print()
        print_summary(db)
        print()
        info("ShoppingMall 시드 완료")
        return 0
    except Exception as exc:
        db.rollback()
        error(str(exc))
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
