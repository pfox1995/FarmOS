import os
import time
import json
import re
import logging
import httpx
import asyncio
from typing import TypedDict, Optional
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.core.database import async_session
from app.models.pesticide import PesticideProduct, PesticideApplication
from sqlalchemy import select
from sqlalchemy.orm import joinedload

load_dotenv()
logger = logging.getLogger(__name__)

class DiagnosisState(TypedDict):
    pest: str
    crop: str
    region: str
    weather_data: Optional[str]
    ncpms_data: Optional[str]
    pesticide_data: Optional[str]
    analysis_result: Optional[dict]

# -----------------
# Caching In-Memory (NCPMS & Weather)
# -----------------
ncpms_cache = {}   # key: (crop, pest) -> (timestamp_sec, data_str)
weather_cache = {} # key: region -> (timestamp_sec, data_str)

NCPMS_CACHE_TTL = 30 * 24 * 3600  # 30일
WEATHER_CACHE_TTL = 3 * 3600      # 3시간
FALLBACK_CROP_NAME = "fallback"

import math
import urllib.parse

def map_to_grid(lat, lon):
    RE = 6371.00877 # 지구 반경(km)
    GRID = 5.0      # 격자 간격(km)
    SLAT1 = 30.0    # 투영 위도1(degree)
    SLAT2 = 60.0    # 투영 위도2(degree)
    OLON = 126.0    # 기준점 경도(degree)
    OLAT = 38.0     # 기준점 위도(degree)
    XO = 43         # 기준점 X좌표(GRID)
    YO = 136        # 기점 Y좌표(GRID)

    DEGRAD = math.pi / 180.0
    RADDEG = 180.0 / math.pi
    
    re = RE / GRID
    slat1 = SLAT1 * DEGRAD
    slat2 = SLAT2 * DEGRAD
    olon = OLON * DEGRAD
    olat = OLAT * DEGRAD

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = math.pow(sf, sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / math.pow(ro, sn)

    ra = math.tan(math.pi * 0.25 + lat * DEGRAD * 0.5)
    ra = re * sf / math.pow(ra, sn)
    theta = lon * DEGRAD - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn
    x = math.floor(ra * math.sin(theta) + XO + 0.5)
    y = math.floor(ro - ra * math.cos(theta) + YO + 0.5)
    return str(int(x)), str(int(y))


def _clean_ai_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _summarize_pesticides_for_prompt(grouped_results: list[dict]) -> str:
    lines: list[str] = []
    for item in grouped_results:
        ingredient_name = str(item.get("ingredient_name", "")).strip()
        products = item.get("products", [])
        if not ingredient_name or not isinstance(products, list):
            continue

        product_names: list[str] = []
        for product in products:
            if not isinstance(product, dict):
                continue

            brand_name = str(product.get("brand_name", "")).strip()
            corporation_name = str(product.get("corporation_name", "")).strip()
            if brand_name and corporation_name:
                product_names.append(f"{brand_name}({corporation_name})")
            elif brand_name:
                product_names.append(brand_name)
            elif corporation_name:
                product_names.append(corporation_name)

        if product_names:
            lines.append(f"- {ingredient_name}: {', '.join(product_names)}")

    return "\n".join(lines) if lines else "권장 농약 정보가 없습니다."


def _extract_json_object(text: str) -> Optional[dict[str, object]]:
    cleaned_text = text.strip()
    cleaned_text = re.sub(r"^```(?:json)?\s*", "", cleaned_text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r"\s*```$", "", cleaned_text)

    try:
        parsed = json.loads(cleaned_text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = cleaned_text.find("{")
    end = cleaned_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(cleaned_text[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return None

    return None


def _build_weather_advice(weather_info: dict) -> str:
    default_advice = (
        "날씨 정보를 충분히 확인하지 못해, 비 예보와 강풍이 없는 이른 아침이나 해질 무렵을 우선 선택하십시오."
    )

    if not isinstance(weather_info, dict):
        return default_advice

    daily_forecast = weather_info.get("daily_forecast") or {}
    if not isinstance(daily_forecast, dict) or not daily_forecast:
        return default_advice

    first_day_key = sorted(daily_forecast.keys())[0]
    first_day = daily_forecast.get(first_day_key, {})
    if not isinstance(first_day, dict):
        first_day = {}

    min_temp = first_day.get("min_temp", "데이터 없음")
    max_temp = first_day.get("max_temp", "데이터 없음")
    rain_prob = first_day.get("max_precip_prob", 0)
    wind_speed = first_day.get("max_wind_speed", 0.0)
    condition = first_day.get("condition", "☀️ 맑음")

    advice_parts: list[str] = []

    try:
        if float(rain_prob) >= 30:
            advice_parts.append("강수 가능성이 있어 비가 오기 전후의 살포는 피하는 것이 좋습니다.")
    except (TypeError, ValueError):
        pass

    try:
        if float(wind_speed) >= 3:
            advice_parts.append("풍속이 다소 높아 약제가 날릴 수 있으니 바람이 약한 시간대를 고르십시오.")
    except (TypeError, ValueError):
        pass

    try:
        if float(max_temp) >= 30:
            advice_parts.append("한낮 고온 시간대는 약해와 증발 손실을 줄이기 위해 피하십시오.")
    except (TypeError, ValueError):
        pass

    if not advice_parts:
        advice_parts.append("비 예보가 없고 바람이 약한 시간대가 유리합니다.")

    if len(first_day_key) == 8 and first_day_key.isdigit():
        display_date = f"{first_day_key[:4]}-{first_day_key[4:6]}-{first_day_key[6:]}"
    else:
        display_date = first_day_key

    advice_parts.append(
        f"첫 예보일({display_date})은 {condition}이며, 기온은 {min_temp}~{max_temp}℃, 강수확률은 {rain_prob}%, 풍속은 {wind_speed}m/s입니다."
    )
    advice_parts.append(
        "이 수치를 기준으로 이른 아침이나 해질 무렵처럼 바람이 약한 시간대를 우선하시고, 비가 오기 전후와 강풍 시간대는 피하십시오."
    )
    return _clean_ai_text(" ".join(advice_parts))


def _build_fallback_strategy_bullets(crop_display: str, pest: str, weather_advice: str) -> list[str]:
    return [
        _clean_ai_text(f"최적 살포 시기: {weather_advice}"),
        _clean_ai_text(
            f"권장 방제법: {crop_display} {pest}는 초기 발생 단계에서 등록된 약제를 안전사용기준에 맞춰 사용하고, NCPMS의 예방 지침을 함께 적용하십시오."
        ),
        "재배 관리: 잡초와 잔재물을 정리하고 예찰을 강화하며, 통풍 확보와 물리적 방제를 병행하십시오.",
    ]


def _build_weather_unavailable_card(message: str) -> str:
    weather_message = _clean_ai_text(message) or "실시간 기상 데이터를 불러오지 못했습니다."
    return (
        "<div class='bg-amber-50 border border-amber-200 rounded-xl p-3 my-3 text-sm text-amber-900'>"
        "<div class='font-semibold mb-1'>⚠️ 기상 데이터 안내</div>"
        f"<div>{weather_message}</div>"
        "</div>"
    )


def _compose_final_response(
    *,
    pest_identification_line: str,
    display_region: str,
    crop_display: str,
    pest: str,
    pest_html: str,
    preventive_info: str,
    weather_summary: str,
    weather_advice: str,
    strategy_bullets: list[str],
) -> str:
    normalized_bullets = [
        _clean_ai_text(bullet).lstrip("-• ").strip()
        for bullet in strategy_bullets
        if _clean_ai_text(bullet)
    ]

    fallback_bullets = _build_fallback_strategy_bullets(
        crop_display=crop_display,
        pest=pest,
        weather_advice=weather_advice,
    )

    while len(normalized_bullets) < 3:
        normalized_bullets.append(fallback_bullets[len(normalized_bullets)])

    normalized_bullets = normalized_bullets[:3]
    weather_advice = _clean_ai_text(weather_advice) or _build_weather_advice({})

    return f"""{pest_identification_line}

## 🌿 {display_region} 지역의 {crop_display} {pest} 방제 솔루션입니다.

## 🧪 권장 농약 목록 (출처: 농촌진흥청 농약안전정보시스템)

{pest_html}

## 🚜 객관적 예방 및 재배적 방제 지침 (출처: 국가농작물병해충관리시스템 NCPMS)

{preventive_info}

## 💡 실시간 환경 맞춤 조언 (출처: 기상청 단기예보 서비스)

- 날씨 요약:
  {weather_summary}
- 조언: {weather_advice}

## 🤖 AI 총평 및 방제 전략

- {normalized_bullets[0]}
- {normalized_bullets[1]}
- {normalized_bullets[2]}

<div class='bg-orange-50 border border-orange-200 rounded-xl p-4 my-4 text-sm text-orange-900'>
  <div class='font-bold flex items-center gap-2 mb-1'>
    <span>⚠️</span> 공지사항
  </div>
  <div class='leading-relaxed'>
    제공된 정보는 공공데이터에 기반한 참고용입니다. 농약 사용 전 반드시 <strong>제품 라벨의 규정</strong>을 확인하십시오.
  </div>
</div>"""

async def fetch_weather(state: DiagnosisState) -> dict:
    region = state.get("region", "서울") # region fields now acts as full address

    now = time.time()
    if region in weather_cache:
        cached_time, cached_data = weather_cache[region]
        if now - cached_time < WEATHER_CACHE_TTL:
            return {"weather_data": cached_data}
            
    from app.core.config import settings
    kakao_key = settings.KAKAO_REST_API_KEY

    api_candidates: list[str] = []
    for candidate in [
        settings.WEATHER_API_KEY,
        settings.KMA_DECODING_KEY,
        settings.KMA_ENCODING_KEY,
    ]:
        normalized = (candidate or "").strip()
        if normalized and normalized not in api_candidates:
            api_candidates.append(normalized)

    if not api_candidates:
        return {"weather_data": {"status": "에러", "message": "API 키 오류"}}

    nx, ny = "60", "127" # default fallback (서울)
    try:
        if kakao_key:
            kakao_url = f"https://dapi.kakao.com/v2/local/search/address.json?query={urllib.parse.quote(region)}"
            headers = {"Authorization": f"KakaoAK {kakao_key}"}
            # requests 대신 httpx 권장이나 bootstrap 시점 호환성 유지
            import requests
            k_resp = requests.get(kakao_url, headers=headers, timeout=5)
            if k_resp.status_code == 200:
                k_data = k_resp.json()
                if k_data.get("documents"):
                    doc = k_data["documents"][0]
                    lat, lon = float(doc["y"]), float(doc["x"])
                    nx, ny = map_to_grid(lat, lon)
    except Exception:
        logger.exception("Kakao API Error for region %s", region)

    # 2. 기상청 단기예보 조회 (약 3일치)
    from datetime import datetime, timedelta
    current_time = datetime.now()
    if current_time.hour < 2 or (current_time.hour == 2 and current_time.minute < 10):
        target = current_time - timedelta(days=1)
        target = target.replace(hour=23, minute=0, second=0)
        base_date, base_time = target.strftime("%Y%m%d"), "2300"
    else:
        base_date, base_time = current_time.strftime("%Y%m%d"), "0200"
    
    url = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
    last_error = "기상청 예보 조회 실패"

    import requests
    for service_key in api_candidates:
        params = {"serviceKey": service_key, "pageNo": "1", "numOfRows": "1000", "dataType": "JSON", "base_date": base_date, "base_time": base_time, "nx": nx, "ny": ny}
        try:
            resp = requests.get(url, params=params, timeout=10)
        except Exception as e:
            last_error = f"기상청 요청 예외: {str(e)}"
            continue

        if resp.status_code != 200:
            last_error = f"기상청 서버 응답 오류({resp.status_code})"
            continue

        try: data = resp.json()
        except Exception: continue

        header = data.get("response", {}).get("header", {})
        if str(header.get("resultCode", "")) not in {"00", "0", "INFO-000"}:
            last_error = f"기상청 API 오류: {header.get('resultMsg')}"
            continue

        items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if not items: continue

        forecast_by_date: dict[str, dict[str, object]] = {}
        for item in items:
            fd, ft, cat, val = item.get("fcstDate"), item.get("fcstTime"), item.get("category"), item.get("fcstValue")
            dt_key = f"{fd}_{ft}"
            if dt_key not in forecast_by_date: forecast_by_date[dt_key] = {}
            forecast_by_date[dt_key][cat] = val

        daily_summary: dict[str, dict[str, object]] = {}
        for dt_key, fcst in forecast_by_date.items():
            d = dt_key.split("_")[0]
            if d not in daily_summary: daily_summary[d] = {"temps": [], "pops": [], "winds": [], "skys": [], "ptys": [], "tmn": None, "tmx": None}
            if "TMP" in fcst: daily_summary[d]["temps"].append(float(fcst["TMP"]))
            if "POP" in fcst: daily_summary[d]["pops"].append(int(fcst["POP"]))
            if "WSD" in fcst: daily_summary[d]["winds"].append(float(fcst["WSD"]))
            if "TMN" in fcst: daily_summary[d]["tmn"] = float(str(fcst["TMN"]).replace("℃", ""))
            if "TMX" in fcst: daily_summary[d]["tmx"] = float(str(fcst["TMX"]).replace("℃", ""))
            if "SKY" in fcst: daily_summary[d]["skys"].append(int(fcst["SKY"]))
            if "PTY" in fcst: daily_summary[d]["ptys"].append(int(fcst["PTY"]))

        formatted_summary = {}
        for d, vals in daily_summary.items():
            min_t = vals["tmn"] if vals["tmn"] is not None else (min(vals["temps"]) if vals["temps"] else None)
            max_t = vals["tmx"] if vals["tmx"] is not None else (max(vals["temps"]) if vals["temps"] else None)
            max_pty, max_sky = max(vals["ptys"]) if vals["ptys"] else 0, max(vals["skys"]) if vals["skys"] else 1
            cond = "☀️ 맑음"
            if max_pty > 0: cond = "❄️ 눈" if max_pty == 3 else "🌧️ 비"
            else:
                if max_sky >= 4: cond = "☁️ 흐림"
                elif max_sky >= 3: cond = "⛅ 구름많음"

            if min_t is not None and max_t is not None:
                formatted_summary[d] = {"min_temp": min_t, "max_temp": max_t, "max_precip_prob": max(vals["pops"]) if vals["pops"] else 0, "max_wind_speed": max(vals["winds"]) if vals["winds"] else 0.0, "condition": cond}

        if formatted_summary:
            w_dict = {"daily_forecast": formatted_summary, "query_address": region, "grid": f"{nx},{ny}"}
            weather_cache[region] = (now, w_dict)
            return {"weather_data": w_dict}

    return {"weather_data": {"status": "에러", "message": last_error}}

from app.models.ncpms import NcpmsDiagnosis

async def fetch_ncpms(state: DiagnosisState) -> dict:
    pest, crop = state.get("pest", "알 수 없음"), state.get("crop", "알 수 없음")
    if not pest or pest == "알수없음": return {"ncpms_data": "해충명 정보가 없습니다."}

    try:
        async with async_session() as db:
            query = select(NcpmsDiagnosis).where(NcpmsDiagnosis.pest_name == pest, NcpmsDiagnosis.crop_name == crop)
            result = await db.execute(query)
            row = result.scalars().first()
            if not row:
                fallback_query = select(NcpmsDiagnosis).where(NcpmsDiagnosis.pest_name == pest, NcpmsDiagnosis.crop_name == FALLBACK_CROP_NAME)
                result = await db.execute(fallback_query)
                row = result.scalars().first()
                
            if row:
                parts = []
                if row.ecology_info: parts.append(f"### {pest} 생태정보\n\n{row.ecology_info.strip()}")
                if row.prevent_method: parts.append(f"### {pest} 방제방법\n\n{row.prevent_method.strip()}")
                return {"ncpms_data": "\n\n".join(parts) if parts else "데이터 없음"}
            return {"ncpms_data": "NCPMS 데이터를 찾을 수 없습니다."}
    except Exception:
        logger.exception("NCPMS DB search error for pest %s", pest)
        return {"ncpms_data": "NCPMS 조회 중 오류가 발생했습니다."}

async def fetch_pesticide(state: DiagnosisState) -> dict:
    pest, crop = state.get("pest", "알 수 없음"), state.get("crop", "알 수 없음")
    try:
        async with async_session() as db:
            query = select(PesticideProduct).where(
                PesticideProduct.target_name.like(f"%{pest}%"),
                PesticideProduct.crop_name.like(f"%{crop}%")
            ).limit(50)
            result = await db.execute(query)
            products = result.scalars().all()
            if not products: return {"pesticide_data": "[]"}

            grouped = {}
            for p in products:
                ing_name = p.ingredient_or_formulation_name or "성분정보없음"
                if ing_name not in grouped:
                    if len(grouped) >= 3: continue
                    grouped[ing_name] = {"ingredient_name": ing_name, "products": []}
                if any(ep["brand_name"] == (p.brand_name or "") for ep in grouped[ing_name]["products"]) or len(grouped[ing_name]["products"]) >= 3:
                    continue
                
                m_raw, t_raw, formulation = (p.application_method or "").strip(), (p.application_timing or "").strip(), (p.formulation_name or "").strip()
                def norm_t(v):
                    if not v or v == "정보없음": return ""
                    return f"수확 {v}일 전까지" if v.isdigit() else v

                v1, v2 = norm_t(m_raw), norm_t(t_raw)
                timing_display = "정보없음"
                if v1 and v2:
                    if v1 == v2: timing_display = v1
                    else:
                        roots = ["정식", "파종", "발생", "수확"]
                        merged = False
                        for r in roots:
                            if r in v1 and r in v2:
                                timing_display = v1 if ("전" in v1 or "후" in v1) else v2
                                merged = True; break
                        if not merged: timing_display = f"{v1} [{v2}]"
                else: timing_display = v1 or v2 or "정보없음"

                action = "살포"
                if "입제" in formulation: action = "토양혼화/처리"
                elif any(f in formulation for f in ["유제", "수화제", "액제", "액상"]): action = "경엽살포"
                
                grouped[ing_name]["products"].append({
                    "brand_name": p.brand_name or "상표명없음",
                    "corporation_name": p.corporation_name or "제조사없음",
                    "application_method": f"{action} ({formulation})" if formulation else action,
                    "application_timing": timing_display,
                    "dilution_text": p.dilution_text or "정보없음",
                    "max_use_count_text": p.max_use_count_text or "정보없음"
                })
            return {"pesticide_data": json.dumps(list(grouped.values()), ensure_ascii=False)}
    except Exception:
        logger.exception("Pesticide fetch error for pest %s", pest)
        return {"pesticide_data": "[]"}

async def generate_diagnosis(state: DiagnosisState) -> dict:
    from app.core.config import settings
    api_key, model_name = settings.OPENROUTER_API_KEY, settings.OPENROUTER_PEST_RAG_MODEL
    if not api_key or api_key == "dummy": return {"analysis_result": {"result_text": "API 키 오류"}}

    try:
        # async with 블록으로 감싸서 리소스 누수 방지 (CoderrabitAI 리뷰 반영)
        async with httpx.AsyncClient(http1=True, http2=False, timeout=httpx.Timeout(180.0, connect=20.0)) as custom_async_client:
            llm = ChatOpenAI(
                model=model_name, api_key=api_key, base_url=settings.OPENROUTER_URL, temperature=0.0,
                http_async_client=custom_async_client,
                model_kwargs={"extra_body": {"reasoning": {"effort": "minimal", "exclude": True}}}
            )

            weather_info = state.get("weather_data", {})
            weather_summary, weather_for_llm = _build_weather_unavailable_card("기상 데이터 없음"), "데이터 없음"
            daily = weather_info.get("daily_forecast") if isinstance(weather_info, dict) else None
            if daily:
                html_cards = ["<div class='grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 my-3'>"]
                for dk, td in daily.items():
                    d_str = f"{dk[:4]}-{dk[4:6]}-{dk[6:]}"
                    html_cards.append(f"<div class='bg-blue-50/50 border border-blue-100 rounded-xl p-3 flex flex-col items-center justify-center text-center shadow-sm'><div class='font-bold text-gray-700 mb-1 text-[13px]'>{d_str}</div><div class='font-medium text-blue-800 text-[13px] mb-1'>{td['condition']}</div><div class='text-xl flex flex-col items-center justify-center font-black text-blue-600 mb-1'><span class='text-[10px] font-normal text-gray-500 bg-white px-2 py-0.5 rounded-full shadow-sm mb-1 mt-1'>최저/최고</span><div>{td['min_temp']}°<span class='text-gray-400 text-sm font-normal mx-1'>/</span>{td['max_temp']}°</div></div><div class='flex flex-col gap-0.5 text-xs text-gray-600 mt-1'><span class='flex items-center justify-center bg-white px-2 py-0.5 rounded border border-blue-100 text-blue-800 font-medium'>☔ 강수 {td['max_precip_prob']}%</span><span class='flex items-center justify-center bg-white px-2 py-0.5 rounded border border-blue-100 text-blue-800 font-medium'>💨 풍속 {td['max_wind_speed']}m/s</span></div></div>")
                html_cards.append("</div>")
                weather_summary = "".join(html_cards)
                fd = daily[sorted(daily.keys())[0]]
                weather_for_llm = f"기온 {fd['min_temp']}~{fd['max_temp']}°C, 강수 {fd['max_precip_prob']}%"

            try: grouped_results = json.loads(state.get("pesticide_data", "[]"))
            except: grouped_results = []

            pest_html = ""
            for item in grouped_results:
                pest_html += f"<div class='bg-gray-50 border border-gray-200 rounded-xl p-4 my-3'><div class='font-bold text-primary mb-3 text-base flex items-center gap-2'><span>💊</span> 성분: {item['ingredient_name']}</div><div class='grid grid-cols-1 md:grid-cols-2 gap-3'>"
                for prod in item.get("products", []):
                    pest_html += f"""<div class='bg-white rounded-lg p-3 shadow-none border border-gray-200 flex flex-col h-full'>
                        <div class='font-bold text-gray-800 text-sm mb-3 flex items-center flex-wrap gap-2'>
                            <span class='text-primary text-[15px]'>{prod['brand_name']}</span>
                            <span class='text-[11px] font-normal text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full'>{prod['corporation_name']}</span>
                        </div>
                        <div class='grid grid-cols-2 gap-2 mt-auto'>
                            <div class='flex flex-col p-1.5 bg-gray-50/50 rounded'>
                                <span class='text-gray-400 mb-0.5 text-[10px]'>방제 방법</span>
                                <span class='font-medium text-gray-700 text-[11px] line-clamp-2' title='{prod['application_method']}'>{prod['application_method']}</span>
                            </div>
                            <div class='flex flex-col p-1.5 bg-gray-50/50 rounded'>
                                <span class='text-gray-400 mb-0.5 text-[10px]'>살포 시기</span>
                                <span class='font-medium text-gray-700 text-[11px] line-clamp-2' title='{prod['application_timing']}'>{prod['application_timing']}</span>
                            </div>
                            <div class='flex flex-col p-1.5 bg-gray-50/50 rounded'>
                                <span class='text-gray-400 mb-0.5 text-[10px]'>희석 배수</span>
                                <span class='font-medium text-gray-700 text-[11px]'>{prod['dilution_text']}</span>
                            </div>
                            <div class='flex flex-col p-1.5 bg-gray-50/50 rounded'>
                                <span class='text-gray-400 mb-0.5 text-[10px]'>사용 횟수</span>
                                <span class='font-medium text-gray-700 text-[11px]'>{prod['max_use_count_text']}</span>
                            </div>
                        </div>
                    </div>"""
                pest_html += "</div></div>"
            if not pest_html: pest_html = "권장 농약 정보가 없습니다."

            pest_name, crop_display = state.get("pest", "알 수 없는 해충"), state.get("crop") or "전체 작물"
            display_region = " ".join(state.get("region", "서울").split()[:2])
            
            json_payload = {"region": display_region, "crop_display": crop_display, "pest": pest_name, "weather_for_llm": weather_for_llm, "preventive_info": state.get("ncpms_data") or "데이터 없음", "pesticide_summary_text": _summarize_pesticides_for_prompt(grouped_results)}
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", "당신은 'FarmOS 해충 진단봇'이며 전문 진단 요약을 생성하는 농업 전문가입니다. 반드시 JSON만 출력하라.\n출력 형식:\n{{\n  \"weather_advice\": \"...\",\n  \"strategy_bullets\": [\"...\", \"...\", \"...\"]\n}}"),
                ("user", "{json_text}")
            ])
            chain = prompt | llm | StrOutputParser()
            raw_res = await chain.ainvoke({"json_text": json.dumps(json_payload, ensure_ascii=False)})
            
            notes = _extract_json_object(raw_res) or {}
            response = _compose_final_response(
                pest_identification_line=f"🔍 입력하신 이미지는 **{pest_name}**(으)로 인식되었습니다.",
                display_region=display_region, crop_display=crop_display, pest=pest_name, pest_html=pest_html,
                preventive_info=state.get("ncpms_data") or "데이터 없음", weather_summary=weather_summary,
                weather_advice=_clean_ai_text(str(notes.get("weather_advice", ""))) or _build_weather_advice(weather_info),
                strategy_bullets=[str(b).lstrip("-• ").strip() for b in notes.get("strategy_bullets", []) if str(b).strip()][:3],
            )
            return {"analysis_result": {"result_text": response}}
    except Exception:
        logger.exception("LLM generation error in diagnosis agent")
        return {"analysis_result": {"result_text": "진단 결과 생성 중 오류가 발생했습니다."}}

workflow = StateGraph(DiagnosisState)
workflow.add_node("fetch_weather", fetch_weather)
workflow.add_node("fetch_ncpms", fetch_ncpms)
workflow.add_node("fetch_pesticide", fetch_pesticide)
workflow.add_node("generate_diagnosis", generate_diagnosis)
workflow.add_edge(START, "fetch_weather")
workflow.add_edge("fetch_weather", "fetch_ncpms")
workflow.add_edge("fetch_ncpms", "fetch_pesticide")
workflow.add_edge("fetch_pesticide", "generate_diagnosis")
workflow.add_edge("generate_diagnosis", END)
diagnosis_app = workflow.compile()

async def run_diagnosis(pest: str, crop: str, region: str):
    initial_state = {"pest": pest, "crop": crop, "region": region, "weather_data": None, "ncpms_data": None, "pesticide_data": None, "analysis_result": None}
    async for event in diagnosis_app.astream(initial_state):
        node_name = list(event.keys())[0]
        yield node_name, dict(event[node_name])
