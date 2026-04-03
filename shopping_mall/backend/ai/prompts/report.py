"""Weekly report prompt templates."""

WEEKLY_REPORT_PROMPT = """당신은 농산물 직거래 쇼핑몰의 비즈니스 분석가입니다.
다음 주간 데이터를 분석하여 경영 인사이트를 한국어로 작성하세요.

기간: {week_start} ~ {week_end}
총 매출: {total_revenue:,}원
총 비용: {total_expense:,}원
순이익: {net_profit:,}원
주문 건수: {order_count}건
인기 상품 TOP 5: {top_items}

다음 내용을 포함하여 3-5문장으로 작성하세요:
1. 매출/이익 트렌드 요약
2. 인기 상품 분석
3. 비용 효율 개선 제안
4. 다음 주 전략 제안

리포트:"""
