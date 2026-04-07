"""KAMIS (농산물유통정보) API 클라이언트 서비스."""

from __future__ import annotations

import httpx

from app.core.config import settings


class KamisService:
    """KAMIS Open API wrapper.

    Endpoints used:
      #1  dailySalesList      — 일별 부류별 도·소매가격정보 (메인)
      #2  periodProductList   — 일별 품목별 도·소매가격정보 (상세)
    """

    BASE_URL = "https://www.kamis.or.kr/service/price/xml.do"
    TIMEOUT = 15  # seconds

    def __init__(self, api_key: str, cert_id: str) -> None:
        self._api_key = api_key
        self._cert_id = cert_id

    # ── helpers ──────────────────────────────────────────────

    def _common_params(self) -> dict[str, str]:
        return {
            "p_cert_key": self._api_key,
            "p_cert_id": self._cert_id,
            "p_returntype": "json",
        }

    async def _get(self, action: str, extra: dict[str, str] | None = None) -> dict:
        params = {"action": action, **self._common_params(), **(extra or {})}
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            resp = await client.get(self.BASE_URL, params=params)
            resp.raise_for_status()
            return resp.json()

    # ── API #1: 일별 부류별 도·소매가격정보 ─────────────────

    async def get_latest_prices(
        self,
        *,
        product_cls_code: str = "",
        item_category_code: str = "",
        country_code: str = "",
    ) -> list[dict]:
        """최신 가격 목록을 반환한다.

        Returns a flat list of item dicts, each containing:
          product_cls_code, category_code, category_name, productno,
          item_name, unit, day1, dpr1, day2, dpr2, day3, dpr3, day4, dpr4,
          direction, value
        """
        raw = await self._get(
            "dailySalesList",
            {
                "p_product_cls_code": product_cls_code,
                "p_item_category_code": item_category_code,
                "p_country_code": country_code,
            },
        )
        return self._extract_daily_sales(raw)

    # ── API #2: 일별 품목별 도·소매가격정보 ─────────────────

    async def get_daily_prices(
        self,
        start_date: str,
        end_date: str,
        item_code: str,
        kind_code: str,
        rank_code: str = "1",
        *,
        product_cls_code: str = "01",
        item_category_code: str = "",
        county_code: str = "",
        convert_kg: str = "Y",
    ) -> dict:
        """일별 가격 데이터를 반환한다."""
        raw = await self._get(
            "periodProductList",
            {
                "p_productclscode": product_cls_code,
                "p_startday": start_date,
                "p_endday": end_date,
                "p_itemcategorycode": item_category_code,
                "p_itemcode": item_code,
                "p_kindcode": kind_code,
                "p_productrankcode": rank_code,
                "p_countycode": county_code,
                "p_convert_kg_yn": convert_kg,
            },
        )
        return self._extract_daily_data(raw)

    # ── response normalizers ────────────────────────────────

    @staticmethod
    def _extract_daily_sales(raw: dict) -> list[dict]:
        """dailySalesList 응답에서 가격 항목 리스트를 추출."""
        try:
            items = raw.get("price", [])
            if isinstance(items, dict):
                items = [items]
            return items if isinstance(items, list) else []
        except (AttributeError, TypeError):
            return []

    @staticmethod
    def _extract_daily_data(raw: dict) -> dict:
        """periodProductList 응답을 정규화."""
        try:
            price_data = raw.get("data", {})

            # error response: {"data": ["001"]}
            if isinstance(price_data, list):
                return {"item_name": "", "kind_name": "", "unit": "", "records": []}

            items = price_data.get("item", [])
            if isinstance(items, dict):
                items = [items]

            return {
                "item_name": items[0].get("itemname", "") if items else "",
                "kind_name": items[0].get("kindname", "") if items else "",
                "unit": items[0].get("unit", "") if items else "",
                "records": items if isinstance(items, list) else [],
            }
        except (AttributeError, TypeError, IndexError):
            return {"item_name": "", "kind_name": "", "unit": "", "records": []}


kamis_service = KamisService(
    api_key=settings.KAMIS_API_KEY,
    cert_id=settings.KAMIS_CERT_ID,
)
