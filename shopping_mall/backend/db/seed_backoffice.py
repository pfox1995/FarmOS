"""Seed the database with backoffice-related dummy data."""
import sys
import os
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, engine, SessionLocal
from app.models import (
    Shipment,
    HarvestSchedule,
    RevenueEntry,
    ExpenseEntry,
    WeeklyReport,
    CustomerSegment,
    ChatLog,
    Order,
    OrderItem,
)


def seed_backoffice():
    """Add backoffice seed data. Assumes base seed.py has already been run."""
    # Create new tables only (don't drop existing)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        now = datetime.utcnow()

        # --- Shipments ---
        shipments = [
            Shipment(
                order_id=2,
                carrier="CJ대한통운",
                tracking_number="6300123456789",
                status="delivered",
                delivered_at=now - timedelta(days=5),
                tracking_history=json.dumps([
                    {"from": "registered", "to": "picked_up", "timestamp": (now - timedelta(days=8)).isoformat()},
                    {"from": "picked_up", "to": "in_transit", "timestamp": (now - timedelta(days=7)).isoformat()},
                    {"from": "in_transit", "to": "delivered", "timestamp": (now - timedelta(days=5)).isoformat()},
                ], ensure_ascii=False),
                created_at=now - timedelta(days=9),
            ),
            Shipment(
                order_id=3,
                carrier="한진택배",
                tracking_number="4200987654321",
                status="in_transit",
                tracking_history=json.dumps([
                    {"from": "registered", "to": "picked_up", "timestamp": (now - timedelta(days=2)).isoformat()},
                    {"from": "picked_up", "to": "in_transit", "timestamp": (now - timedelta(days=1)).isoformat()},
                ], ensure_ascii=False),
                created_at=now - timedelta(days=3),
            ),
            Shipment(
                order_id=6,
                carrier="로젠택배",
                tracking_number="9100555666777",
                status="picked_up",
                tracking_history=json.dumps([
                    {"from": "registered", "to": "picked_up", "timestamp": (now - timedelta(hours=12)).isoformat()},
                ], ensure_ascii=False),
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
                tracking_history=json.dumps([
                    {"from": "registered", "to": "picked_up", "timestamp": (now - timedelta(days=13)).isoformat()},
                    {"from": "picked_up", "to": "in_transit", "timestamp": (now - timedelta(days=12)).isoformat()},
                    {"from": "in_transit", "to": "delivered", "timestamp": (now - timedelta(days=10)).isoformat()},
                ], ensure_ascii=False),
                created_at=now - timedelta(days=14),
            ),
        ]
        db.add_all(shipments)
        db.flush()

        # --- Harvest Schedules ---
        harvest_schedules = [
            HarvestSchedule(product_id=1, harvest_date="2026-04-05", estimated_quantity=500, actual_quantity=480, status="harvested"),
            HarvestSchedule(product_id=3, harvest_date="2026-04-08", estimated_quantity=300, status="planned"),
            HarvestSchedule(product_id=6, harvest_date="2026-04-03", estimated_quantity=1000, actual_quantity=1050, status="shipped"),
            HarvestSchedule(product_id=7, harvest_date="2026-04-10", estimated_quantity=600, status="planned"),
            HarvestSchedule(product_id=11, harvest_date="2026-04-02", estimated_quantity=200, actual_quantity=190, status="harvested"),
            HarvestSchedule(product_id=16, harvest_date="2026-04-15", estimated_quantity=800, status="planned"),
            HarvestSchedule(product_id=21, harvest_date="2026-04-12", estimated_quantity=100, status="planned"),
            HarvestSchedule(product_id=26, harvest_date="2026-04-20", estimated_quantity=400, status="planned"),
        ]
        db.add_all(harvest_schedules)
        db.flush()

        # --- Revenue Entries (from existing orders) ---
        orders = db.query(Order).filter(Order.status.in_(["paid", "shipping", "delivered"])).all()
        revenue_entries = []
        for order in orders:
            items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
            for item in items:
                revenue_entries.append(RevenueEntry(
                    date=order.created_at.strftime("%Y-%m-%d") if order.created_at else "2026-03-15",
                    order_id=order.id,
                    product_id=item.product_id,
                    quantity=item.quantity,
                    unit_price=item.price // item.quantity if item.quantity else item.price,
                    total_amount=item.price,
                    category="sales",
                ))
        db.add_all(revenue_entries)
        db.flush()

        # --- Expense Entries ---
        expenses = [
            ExpenseEntry(date="2026-03-15", description="택배 박스 500개 구매", amount=150000, category="packaging"),
            ExpenseEntry(date="2026-03-16", description="CJ대한통운 택배비 월정산", amount=320000, category="shipping"),
            ExpenseEntry(date="2026-03-18", description="유기농 비료 20kg", amount=85000, category="material"),
            ExpenseEntry(date="2026-03-20", description="포장 아르바이트 3명 일당", amount=270000, category="labor"),
            ExpenseEntry(date="2026-03-22", description="온실 전기요금", amount=180000, category="utility"),
            ExpenseEntry(date="2026-03-25", description="인스타그램 광고비", amount=200000, category="marketing"),
            ExpenseEntry(date="2026-03-27", description="아이스팩 1000개", amount=120000, category="packaging"),
            ExpenseEntry(date="2026-03-28", description="종자 구입 (토마토, 상추)", amount=95000, category="material"),
            ExpenseEntry(date="2026-03-30", description="배송차량 유류비", amount=150000, category="shipping"),
            ExpenseEntry(date="2026-04-01", description="사무실 인터넷 요금", amount=55000, category="utility"),
        ]
        db.add_all(expenses)
        db.flush()

        # --- Weekly Reports ---
        reports = [
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
        db.add_all(reports)
        db.flush()

        # --- Customer Segments ---
        segment_data = [
            (1, "repeat", 5, 2, 120000),
            (2, "loyal", 10, 3, 280000),
            (3, "new", 15, 1, 52000),
            (4, "vip", 3, 5, 650000),
            (5, "at_risk", 75, 2, 95000),
        ]
        segments = []
        for user_id, segment, recency, freq, monetary in segment_data:
            segments.append(CustomerSegment(
                user_id=user_id,
                segment=segment,
                recency_days=recency,
                frequency=freq,
                monetary=monetary,
                last_updated=now,
            ))
        db.add_all(segments)
        db.flush()

        # --- Chat Logs ---
        chat_logs = [
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
        db.add_all(chat_logs)
        db.commit()

        print("Backoffice seed completed successfully!")
        print(f"  - {len(shipments)} shipments")
        print(f"  - {len(harvest_schedules)} harvest schedules")
        print(f"  - {len(revenue_entries)} revenue entries")
        print(f"  - {len(expenses)} expense entries")
        print(f"  - {len(reports)} weekly reports")
        print(f"  - {len(segments)} customer segments")
        print(f"  - {len(chat_logs)} chat logs")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_backoffice()
