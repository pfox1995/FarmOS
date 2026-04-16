"""한국천문연구원 특일 정보제공 서비스 클라이언트.

공공데이터포털 API를 사용하여 공휴일 정보를 조회합니다.
조회 결과는 (year, month) 기준으로 메모리 캐싱합니다.

API 문서: OpenAPI활용가이드_한국천문연구원_천문우주정보__특일_정보제공_서비스_v1.4
엔드포인트: getRestDeInfo (공휴일 정보조회)
"""
import logging
from datetime import date, timedelta

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = "http://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo"

# (year, month) → 공휴일 날짜 set
_cache: dict[tuple[int, int], set[date]] = {}


async def _fetch_holidays(year: int, month: int, api_key: str) -> set[date]:
    """API 호출로 해당 연월의 공휴일(isHoliday=Y) 날짜 set을 반환."""
    params = {
        "solYear": str(year),
        "solMonth": f"{month:02d}",
        "ServiceKey": api_key,
        "_type": "json",
        "numOfRows": "50",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(_BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        items = (
            data.get("response", {})
                .get("body", {})
                .get("items", {})
                .get("item", [])
        )
        # 단일 항목인 경우 dict로 올 수 있음
        if isinstance(items, dict):
            items = [items]

        holidays = set()
        for item in items:
            if item.get("isHoliday") == "Y":
                locdate = str(item.get("locdate", ""))
                if len(locdate) == 8:
                    holidays.add(date(int(locdate[:4]), int(locdate[4:6]), int(locdate[6:])))

        return holidays

    except (httpx.HTTPError, KeyError, ValueError) as e:
        logger.warning("공휴일 API 조회 실패 (%d-%02d): %s", year, month, e)
        return set()


async def get_holidays(year: int, month: int, api_key: str) -> set[date]:
    """캐싱된 공휴일 set 반환. 캐시 없으면 API 호출."""
    key = (year, month)
    if key not in _cache:
        _cache[key] = await _fetch_holidays(year, month, api_key)
    return _cache[key]


async def next_business_day(target: date, api_key: str) -> tuple[date, list[str]]:
    """target 날짜가 주말/공휴일이면 다음 영업일을 반환.

    Returns:
        (adjusted_date, skipped_reasons)
        - adjusted_date: 조정된 배송 예정일
        - skipped_reasons: 건너뛴 이유 목록 (예: ["토요일", "어린이날"])
    """
    skipped: list[str] = []
    current = target

    # 최대 14일 탐색 (연휴 대비)
    for _ in range(14):
        weekday = current.weekday()  # 0=월 ... 6=일

        if weekday == 5:
            skipped.append(f"{current.month}/{current.day} 토요일")
            current += timedelta(days=1)
            continue

        if weekday == 6:
            skipped.append(f"{current.month}/{current.day} 일요일")
            current += timedelta(days=1)
            continue

        # 해당 월 공휴일 조회
        holidays = await get_holidays(current.year, current.month, api_key)
        if current in holidays:
            # 공휴일 이름 찾기 (로그용)
            skipped.append(f"{current.month}/{current.day} 공휴일")
            current += timedelta(days=1)
            continue

        # 영업일
        break

    return current, skipped
