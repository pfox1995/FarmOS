"""Seed the database with dummy Korean shopping mall data."""
import sys
import os
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, engine, SessionLocal
from app.models import Category, Store, Product, User, CartItem, Order, OrderItem, Review, Wishlist


def seed():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Categories
        parents = [
            Category(id=1, name="과일", icon="apple", sort_order=1),
            Category(id=2, name="채소", icon="carrot", sort_order=2),
            Category(id=3, name="축산", icon="meat", sort_order=3),
            Category(id=4, name="수산", icon="fish", sort_order=4),
        ]
        db.add_all(parents)
        db.flush()

        children = [
            Category(id=5, name="사과/배", parent_id=1, sort_order=1),
            Category(id=6, name="감귤/오렌지", parent_id=1, sort_order=2),
            Category(id=7, name="엽채류", parent_id=2, sort_order=1),
            Category(id=8, name="근채류", parent_id=2, sort_order=2),
            Category(id=9, name="소고기", parent_id=3, sort_order=1),
            Category(id=10, name="돼지고기", parent_id=3, sort_order=2),
            Category(id=11, name="생선", parent_id=4, sort_order=1),
            Category(id=12, name="해산물", parent_id=4, sort_order=2),
        ]
        db.add_all(children)
        db.flush()

        # Stores
        stores = [
            Store(id=1, name="행복한 과수원", description="신선한 과일을 산지에서 직접 배송합니다.", image_url="https://picsum.photos/seed/store1/200/200", rating=4.8, product_count=10),
            Store(id=2, name="신선한 채소밭", description="무농약 유기농 채소를 재배합니다.", image_url="https://picsum.photos/seed/store2/200/200", rating=4.6, product_count=10),
            Store(id=3, name="한우마을", description="1++ 등급 한우 전문 농장입니다.", image_url="https://picsum.photos/seed/store3/200/200", rating=4.9, product_count=8),
            Store(id=4, name="바다의선물", description="당일 경매 신선한 수산물을 직송합니다.", image_url="https://picsum.photos/seed/store4/200/200", rating=4.7, product_count=8),
            Store(id=5, name="농부의정성", description="정성 가득 유기농 농산물 전문점입니다.", image_url="https://picsum.photos/seed/store5/200/200", rating=4.5, product_count=6),
        ]
        db.add_all(stores)
        db.flush()

        now = datetime.utcnow()
        products_data = [
            dict(name="경북 부사 사과 5kg", description="아삭하고 달콤한 경북 부사 사과입니다.", price=29900, discount_rate=10, category_id=5, store_id=1, stock=100, rating=4.8, review_count=45, sales_count=320),
            dict(name="충남 신고배 7.5kg", description="과즙 풍부한 충남 신고배입니다.", price=35000, discount_rate=15, category_id=5, store_id=1, stock=80, rating=4.7, review_count=32, sales_count=210),
            dict(name="청송 꿀사과 3kg", description="청송 고산지 재배 꿀사과, 당도 14brix 이상.", price=22000, discount_rate=5, category_id=5, store_id=1, stock=150, rating=4.9, review_count=67, sales_count=450),
            dict(name="나주배 선물세트 5kg", description="명절 선물용 나주배 특선 세트입니다.", price=45000, discount_rate=20, category_id=5, store_id=5, stock=60, rating=4.6, review_count=23, sales_count=180),
            dict(name="홍로사과 2kg", description="새콤달콤한 홍로사과, 간식으로 제격!", price=15000, discount_rate=0, category_id=5, store_id=1, stock=200, rating=4.5, review_count=18, sales_count=130),
            dict(name="제주 감귤 5kg", description="제주도 직송 노지 감귤입니다.", price=18900, discount_rate=10, category_id=6, store_id=1, stock=200, rating=4.7, review_count=88, sales_count=520),
            dict(name="제주 한라봉 3kg", description="달콤한 향이 가득한 한라봉입니다.", price=28000, discount_rate=15, category_id=6, store_id=1, stock=120, rating=4.8, review_count=55, sales_count=380),
            dict(name="카라카라 오렌지 2kg", description="붉은 과육의 수입 카라카라 오렌지.", price=16000, discount_rate=5, category_id=6, store_id=5, stock=90, rating=4.4, review_count=12, sales_count=95),
            dict(name="천혜향 2kg", description="제주 천혜향, 향긋한 프리미엄 감귤.", price=32000, discount_rate=10, category_id=6, store_id=1, stock=70, rating=4.9, review_count=41, sales_count=290),
            dict(name="레드향 3kg", description="레드향 특대 사이즈, 선물용으로 좋습니다.", price=38000, discount_rate=20, category_id=6, store_id=5, stock=50, rating=4.6, review_count=29, sales_count=200),
            dict(name="유기농 상추 300g", description="무농약 유기농 상추, 쌈채소로 최고!", price=3500, discount_rate=0, category_id=7, store_id=2, stock=300, rating=4.5, review_count=22, sales_count=180),
            dict(name="깻잎 100매", description="향긋한 국내산 깻잎 100매입니다.", price=4500, discount_rate=10, category_id=7, store_id=2, stock=250, rating=4.6, review_count=35, sales_count=240),
            dict(name="시금치 500g", description="뿌리까지 먹을 수 있는 신선한 시금치.", price=4000, discount_rate=5, category_id=7, store_id=2, stock=200, rating=4.4, review_count=15, sales_count=120),
            dict(name="배추 1포기", description="절임용/국물용 배추 1포기.", price=5500, discount_rate=0, category_id=7, store_id=2, stock=150, rating=4.3, review_count=10, sales_count=90),
            dict(name="청경채 200g", description="아삭한 식감의 미니 청경채.", price=3000, discount_rate=0, category_id=7, store_id=5, stock=180, rating=4.5, review_count=8, sales_count=70),
            dict(name="감자 3kg", description="포슬포슬한 강원도 감자입니다.", price=8900, discount_rate=10, category_id=8, store_id=2, stock=180, rating=4.6, review_count=40, sales_count=310),
            dict(name="고구마 3kg", description="꿀고구마, 촉촉하고 달콤합니다.", price=12000, discount_rate=15, category_id=8, store_id=2, stock=160, rating=4.8, review_count=52, sales_count=400),
            dict(name="당근 1kg", description="제주 무농약 당근, 주스용으로 좋습니다.", price=4500, discount_rate=5, category_id=8, store_id=2, stock=220, rating=4.4, review_count=18, sales_count=140),
            dict(name="양파 3kg", description="국내산 양파 3kg, 요리 필수재료.", price=6500, discount_rate=0, category_id=8, store_id=5, stock=300, rating=4.3, review_count=25, sales_count=200),
            dict(name="무 1개", description="시원한 국물맛을 내는 겨울무.", price=3000, discount_rate=0, category_id=8, store_id=2, stock=200, rating=4.2, review_count=9, sales_count=85),
            dict(name="한우 등심 1++ 300g", description="최상급 1++ 한우 등심, 마블링이 뛰어납니다.", price=52000, discount_rate=10, category_id=9, store_id=3, stock=50, rating=4.9, review_count=78, sales_count=420),
            dict(name="한우 갈비살 500g", description="구이용 한우 갈비살, 부드러운 식감.", price=45000, discount_rate=15, category_id=9, store_id=3, stock=60, rating=4.8, review_count=62, sales_count=350),
            dict(name="한우 채끝 200g", description="스테이크용 한우 채끝살.", price=38000, discount_rate=5, category_id=9, store_id=3, stock=40, rating=4.7, review_count=33, sales_count=210),
            dict(name="한우 불고기용 300g", description="양념 불고기용 얇은 슬라이스.", price=28000, discount_rate=20, category_id=9, store_id=3, stock=90, rating=4.6, review_count=45, sales_count=380),
            dict(name="한우 사골 2kg", description="진한 사골국물용 한우 사골.", price=22000, discount_rate=10, category_id=9, store_id=3, stock=70, rating=4.5, review_count=20, sales_count=160),
            dict(name="제주 흑돼지 삼겹살 500g", description="제주 흑돼지 두툼한 삼겹살.", price=25000, discount_rate=10, category_id=10, store_id=3, stock=100, rating=4.8, review_count=90, sales_count=600),
            dict(name="목살 구이용 500g", description="부드러운 목살, 구이에 최적.", price=18000, discount_rate=5, category_id=10, store_id=3, stock=120, rating=4.6, review_count=42, sales_count=280),
            dict(name="돼지갈비 양념 1kg", description="달콤한 양념 돼지갈비, 바로 구워 드세요.", price=22000, discount_rate=15, category_id=10, store_id=3, stock=80, rating=4.7, review_count=55, sales_count=350),
            dict(name="노르웨이 생연어 300g", description="신선한 노르웨이산 생연어 슬라이스.", price=18900, discount_rate=10, category_id=11, store_id=4, stock=100, rating=4.7, review_count=65, sales_count=450),
            dict(name="제주 광어회 500g", description="제주 자연산 광어 활어회.", price=35000, discount_rate=5, category_id=11, store_id=4, stock=40, rating=4.8, review_count=38, sales_count=220),
            dict(name="고등어 2마리", description="국내산 고등어, 구이/조림용.", price=8900, discount_rate=0, category_id=11, store_id=4, stock=150, rating=4.5, review_count=28, sales_count=200),
            dict(name="참치회 400g", description="냉동참치 뱃살+등살 모둠회.", price=29000, discount_rate=15, category_id=11, store_id=4, stock=60, rating=4.6, review_count=30, sales_count=190),
            dict(name="갈치 2마리", description="제주 은갈치, 두툼하고 고소합니다.", price=24000, discount_rate=10, category_id=11, store_id=4, stock=70, rating=4.7, review_count=22, sales_count=170),
            dict(name="통영 생굴 1kg", description="통영 직송 신선한 생굴.", price=15000, discount_rate=10, category_id=12, store_id=4, stock=80, rating=4.8, review_count=48, sales_count=320),
            dict(name="킹크랩 1마리 (1.5kg)", description="러시아산 활 킹크랩.", price=89000, discount_rate=5, category_id=12, store_id=4, stock=20, rating=4.9, review_count=15, sales_count=80),
            dict(name="새우 (대) 1kg", description="활 대하 1kg, 구이/찜용.", price=28000, discount_rate=10, category_id=12, store_id=4, stock=90, rating=4.6, review_count=35, sales_count=250),
            dict(name="전복 10마리", description="완도산 활전복, 크기 균일.", price=35000, discount_rate=15, category_id=12, store_id=4, stock=60, rating=4.7, review_count=25, sales_count=180),
            dict(name="오징어 3마리", description="국내산 싱싱한 오징어.", price=12000, discount_rate=0, category_id=12, store_id=4, stock=110, rating=4.4, review_count=18, sales_count=140),
            dict(name="유기농 블루베리 500g", description="국내 유기농 블루베리, 항산화 풍부.", price=16000, discount_rate=10, category_id=6, store_id=5, stock=100, rating=4.7, review_count=33, sales_count=250),
            dict(name="친환경 방울토마토 1kg", description="당도 높은 대추방울토마토.", price=9500, discount_rate=5, category_id=7, store_id=5, stock=180, rating=4.6, review_count=27, sales_count=200),
            dict(name="유기농 브로콜리 2개", description="무농약 유기농 브로콜리.", price=5500, discount_rate=0, category_id=7, store_id=5, stock=150, rating=4.4, review_count=12, sales_count=100),
            dict(name="흙당근 2kg", description="껍질째 먹는 유기농 흙당근.", price=8000, discount_rate=10, category_id=8, store_id=5, stock=130, rating=4.5, review_count=15, sales_count=110),
        ]

        products = []
        for i, pd in enumerate(products_data, 1):
            pd["id"] = i
            pd["thumbnail"] = f"https://picsum.photos/seed/product{i}/400/400"
            pd["images"] = json.dumps([f"https://picsum.photos/seed/product{i}a/600/600", f"https://picsum.photos/seed/product{i}b/600/600", f"https://picsum.photos/seed/product{i}c/600/600"])
            pd["options"] = json.dumps(["기본"])
            pd["created_at"] = now - timedelta(days=42 - i)
            products.append(Product(**pd))
        db.add_all(products)
        db.flush()

        # Users
        users = [
            User(id=1, name="김민수", email="minsu@example.com", phone="010-1234-5678", address=json.dumps({"zipcode": "06234", "address": "서울시 강남구 역삼동 123-45", "detail": "아파트 101동 202호"}, ensure_ascii=False)),
            User(id=2, name="이지은", email="jieun@example.com", phone="010-2345-6789", address=json.dumps({"zipcode": "04523", "address": "서울시 중구 명동 67-8", "detail": "오피스텔 301호"}, ensure_ascii=False)),
            User(id=3, name="박준혁", email="junhyuk@example.com", phone="010-3456-7890", address=json.dumps({"zipcode": "13487", "address": "경기도 성남시 분당구 정자동 45-6", "detail": ""}, ensure_ascii=False)),
            User(id=4, name="최수연", email="sooyeon@example.com", phone="010-4567-8901", address=json.dumps({"zipcode": "48058", "address": "부산시 해운대구 우동 789-10", "detail": "빌라 2층"}, ensure_ascii=False)),
            User(id=5, name="정하늘", email="haneul@example.com", phone="010-5678-9012", address=json.dumps({"zipcode": "61452", "address": "광주시 동구 충장로 12-3", "detail": "주택"}, ensure_ascii=False)),
        ]
        db.add_all(users)
        db.flush()

        # Reviews
        review_contents = [
            "정말 신선하고 맛있어요! 재구매 의사 100%입니다.",
            "배송이 빨라서 좋았어요. 품질도 만족합니다.",
            "가격 대비 양이 넉넉해서 좋아요.",
            "선물용으로 구매했는데 포장이 깔끔합니다.",
            "아이들이 너무 잘 먹어요. 또 주문할게요!",
            "향이 좋고 식감이 아삭아삭해요.",
            "기대 이상이었어요. 강력 추천합니다!",
            "약간 작은 것도 있었지만 전체적으로 만족해요.",
            "매번 주문하는데 한결같은 품질이에요.",
            "친구 추천으로 구매했는데 정말 좋네요.",
            "조리해서 먹었는데 정말 부드럽고 맛있었어요.",
            "냉동 상태가 아주 좋았어요. 해동 후에도 신선합니다.",
            "이 가격에 이 품질이면 최고입니다.",
            "포장이 꼼꼼하게 되어 있어서 안심하고 먹을 수 있어요.",
            "반찬으로 만들어 먹으니 온 가족이 좋아해요.",
            "오래 기다린 보람이 있네요. 맛이 일품입니다.",
            "사진이랑 실물이 똑같아요! 만족합니다.",
            "신선도가 좋아서 회로 먹기 딱 좋았어요.",
            "양념이 잘 되어 있어서 바로 구워 먹었어요.",
            "건강한 먹거리를 찾는 분들께 추천드립니다.",
            "매주 정기배송 받고 있는데 항상 만족스러워요.",
            "선물 받은 분이 너무 좋아하셨어요.",
            "비린내 없이 깔끔한 맛이에요.",
            "유기농이라 안심하고 먹을 수 있어요.",
            "두 번째 구매인데 역시 기대를 저버리지 않네요.",
            "살짝 아쉬운 점도 있지만 전체적으로 좋아요.",
            "가성비 갑! 다음에도 꼭 구매할게요.",
            "택배 기사님이 조심히 배달해주셔서 상태가 좋았어요.",
            "캠핑 갈 때 가져갔는데 모두 맛있다고 했어요.",
            "식감이 아주 좋고 고소한 맛이 일품이에요.",
        ]
        reviews = []
        for i in range(30):
            reviews.append(Review(
                id=i + 1,
                product_id=(i % 42) + 1,
                user_id=(i % 5) + 1,
                rating=round(3.5 + (i % 4) * 0.4, 1),
                content=review_contents[i],
                images=json.dumps([f"https://picsum.photos/seed/review{i+1}/300/300"]) if i % 3 == 0 else None,
                created_at=now - timedelta(days=30 - i, hours=i),
            ))
        db.add_all(reviews)
        db.flush()

        # Orders
        statuses = ["pending", "paid", "shipping", "delivered", "delivered", "paid", "shipping", "delivered", "cancelled", "delivered"]
        orders = []
        for i in range(10):
            o = Order(
                id=i + 1,
                user_id=(i % 5) + 1,
                total_price=0,
                status=statuses[i],
                shipping_address=json.dumps({"zipcode": "06234", "address": "서울시 강남구 역삼동", "detail": f"테스트 {i+1}호"}, ensure_ascii=False),
                payment_method="card" if i % 2 == 0 else "bank_transfer",
                created_at=now - timedelta(days=20 - i * 2),
            )
            orders.append(o)
        db.add_all(orders)
        db.flush()

        order_items = []
        total_prices = [0] * 10
        for i in range(10):
            num_items = (i % 3) + 1
            for j in range(num_items):
                pid = (i * 3 + j) % 42 + 1
                prod = products[pid - 1]
                discounted = prod.price * (100 - prod.discount_rate) // 100
                qty = (j % 3) + 1
                item_price = discounted * qty
                total_prices[i] += item_price
                order_items.append(OrderItem(
                    order_id=i + 1,
                    product_id=pid,
                    quantity=qty,
                    price=item_price,
                    selected_option=json.dumps("기본"),
                ))
        db.add_all(order_items)
        db.flush()
        for i, o in enumerate(orders):
            o.total_price = total_prices[i]
        db.flush()

        # Cart Items
        cart_items = [
            CartItem(user_id=1, product_id=1, quantity=2, selected_option=json.dumps("기본")),
            CartItem(user_id=1, product_id=6, quantity=1, selected_option=json.dumps("기본")),
            CartItem(user_id=1, product_id=21, quantity=1, selected_option=json.dumps("기본")),
            CartItem(user_id=2, product_id=3, quantity=3, selected_option=json.dumps("기본")),
            CartItem(user_id=2, product_id=17, quantity=1, selected_option=json.dumps("기본")),
        ]
        db.add_all(cart_items)
        db.flush()

        # Wishlists
        wishlists = [
            Wishlist(user_id=1, product_id=1),
            Wishlist(user_id=1, product_id=7),
            Wishlist(user_id=1, product_id=21),
            Wishlist(user_id=1, product_id=34),
            Wishlist(user_id=2, product_id=3),
            Wishlist(user_id=2, product_id=26),
            Wishlist(user_id=3, product_id=9),
            Wishlist(user_id=3, product_id=29),
        ]
        db.add_all(wishlists)
        db.commit()

        print("Seed completed successfully!")
        print(f"  - {len(parents) + len(children)} categories")
        print(f"  - {len(stores)} stores")
        print(f"  - {len(products)} products")
        print(f"  - {len(users)} users")
        print(f"  - {len(reviews)} reviews")
        print(f"  - {len(orders)} orders with {len(order_items)} items")
        print(f"  - {len(cart_items)} cart items")
        print(f"  - {len(wishlists)} wishlists")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
