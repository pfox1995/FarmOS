"""농산물 시세 (KAMIS) API 라우터."""

from fastapi import APIRouter, Depends, HTTPException, Query
from httpx import HTTPError

from app.core.deps import get_current_user
from app.services.kamis import kamis_service

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/latest", dependencies=[Depends(get_current_user)])
async def get_latest_prices(
    product_cls_code: str = Query("", description="01:소매, 02:도매, 빈값:전체"),
    item_category_code: str = Query("", description="부류코드 (빈값=전체)"),
    country_code: str = Query("", description="지역코드 (빈값=전국평균)"),
) -> dict:
    """일별 부류별 도·소매가격정보 (API #1 dailySalesList)."""
    try:
        items = await kamis_service.get_latest_prices(
            product_cls_code=product_cls_code,
            item_category_code=item_category_code,
            country_code=country_code,
        )
        return {"items": items}
    except HTTPError:
        raise HTTPException(502, "KAMIS API 연결에 실패했습니다.")
    except Exception:
        raise HTTPException(502, "KAMIS 응답 형식이 올바르지 않습니다.")


@router.get("/daily", dependencies=[Depends(get_current_user)])
async def get_daily_prices(
    start_date: str = Query(..., description="시작일 (YYYY-MM-DD)"),
    end_date: str = Query(..., description="종료일 (YYYY-MM-DD)"),
    item_code: str = Query(..., description="품목코드"),
    kind_code: str = Query(..., description="품종코드"),
    rank_code: str = Query("1", description="등급코드"),
    product_cls_code: str = Query("01", description="01:소매, 02:도매"),
    item_category_code: str = Query("", description="부류코드"),
    county_code: str = Query("", description="지역코드"),
) -> dict:
    """일별 품목별 도·소매가격정보 (API #2 periodProductList)."""
    try:
        data = await kamis_service.get_daily_prices(
            start_date=start_date,
            end_date=end_date,
            item_code=item_code,
            kind_code=kind_code,
            rank_code=rank_code,
            product_cls_code=product_cls_code,
            item_category_code=item_category_code,
            county_code=county_code,
        )
        return data
    except HTTPError:
        raise HTTPException(502, "KAMIS API 연결에 실패했습니다.")
    except Exception:
        raise HTTPException(502, "KAMIS 응답 형식이 올바르지 않습니다.")
