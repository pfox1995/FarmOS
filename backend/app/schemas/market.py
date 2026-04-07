"""KAMIS 시세 API 응답 스키마."""

from pydantic import BaseModel


class MarketItemPrice(BaseModel):
    """API #6 — 최근일자 가격 항목 하나."""

    item_name: str = ""
    item_code: str = ""
    kind_name: str = ""
    kind_code: str = ""
    rank: str = ""
    rank_code: str = ""
    unit: str = ""
    day1: str = ""  # 당일
    dpr1: str = ""  # 당일 가격
    day2: str = ""  # 1일 전
    dpr2: str = ""  # 1일 전 가격
    day3: str = ""  # 1주일 전
    dpr3: str = ""  # 1주일 전 가격
    day4: str = ""  # 2주일 전
    dpr4: str = ""  # 2주일 전 가격
    day5: str = ""  # 1개월 전
    dpr5: str = ""  # 1개월 전 가격
    day6: str = ""  # 1년 전
    dpr6: str = ""  # 1년 전 가격
    day7: str = ""
    dpr7: str = ""


class LatestPricesResponse(BaseModel):
    items: list[MarketItemPrice]


class PriceTrendPoint(BaseModel):
    """API #7 — 날짜별 가격 데이터 포인트."""

    date: str = ""
    price: str = ""


class TrendsResponse(BaseModel):
    item_name: str = ""
    kind_name: str = ""
    unit: str = ""
    prices: list[dict] = []


class DailyPriceRecord(BaseModel):
    """API #2 — 일별 가격 레코드."""

    date: str = ""
    price: str = ""


class DailyPricesResponse(BaseModel):
    item_name: str = ""
    kind_name: str = ""
    unit: str = ""
    records: list[dict] = []
