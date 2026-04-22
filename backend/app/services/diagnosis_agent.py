import os
import time
import json
import re
from typing import TypedDict, Optional
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.core.database import async_session
from app.models.pesticide import PesticideProduct
from sqlalchemy import select

load_dotenv()

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

## ⚠️ 공지: 제공된 정보는 공공데이터에 기반한 참고용입니다. 농약 사용 전 반드시 제품 라벨의 규정을 확인하십시오."""

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

    import requests
    from datetime import datetime, timedelta
    
    # 1. Kakao API로 주소를 좌표로 변환
    nx, ny = "60", "127" # default fallback (서울)
    try:
        if kakao_key:
            kakao_url = f"https://dapi.kakao.com/v2/local/search/address.json?query={urllib.parse.quote(region)}"
            headers = {"Authorization": f"KakaoAK {kakao_key}"}
            k_resp = requests.get(kakao_url, headers=headers, timeout=5)
            if k_resp.status_code == 200:
                k_data = k_resp.json()
                if k_data.get("documents"):
                    doc = k_data["documents"][0]
                    lat = float(doc["y"])
                    lon = float(doc["x"])
                    nx, ny = map_to_grid(lat, lon)
    except Exception as e:
        print("Kakao API Error:", e)

    # 2. 기상청 단기예보 조회 (약 3일치)
    current_time = datetime.now()
    # 단기예보는 0200, 0500, 0800 등에 발표
    # 일최저/일최고 기온(TMN, TMX)을 포함해 온전한 하루 데이터를 얻기 위해, 
    # 항상 그날의 가장 이른 발표 시각(02:00)이나 전날 23:00 예보를 기준으로 조회하도록 시간 조정
    if current_time.hour < 2 or (current_time.hour == 2 and current_time.minute < 10):
        target = current_time - timedelta(days=1)
        target = target.replace(hour=23, minute=0, second=0)
        base_date = target.strftime("%Y%m%d")
        base_time = "2300"
    else:
        base_date = current_time.strftime("%Y%m%d")
        base_time = "0200"
    
    url = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
    last_error = "기상청 예보 조회 실패"

    # numOfRows=1000 정도면 02:00 발표 기준 미래 3일치 전체(TMN, TMX 포함) 조회 가능
    for service_key in api_candidates:
        params = {
            "serviceKey": service_key,
            "pageNo": "1",
            "numOfRows": "1000",
            "dataType": "JSON",
            "base_date": base_date,
            "base_time": base_time,
            "nx": nx,
            "ny": ny,
        }

        try:
            resp = requests.get(url, params=params, timeout=10)
        except Exception as e:
            last_error = f"기상청 요청 예외: {str(e)}"
            continue

        raw_text = resp.text.strip()
        if resp.status_code != 200:
            last_error = f"기상청 서버 응답 오류({resp.status_code})"
            continue
        if raw_text == "Unauthorized":
            last_error = "기상청 API 인증 오류(Unauthorized)"
            continue

        try:
            data = resp.json()
        except Exception:
            last_error = "기상청 응답 파싱 오류(JSON 아님)"
            continue

        header = data.get("response", {}).get("header", {})
        result_code = str(header.get("resultCode", "")).strip()
        result_msg = str(header.get("resultMsg", "")).strip()
        if result_code not in {"00", "0", "INFO-000"}:
            last_error = f"기상청 API 오류({result_code}): {result_msg or '원인 불명'}"
            continue

        items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if not isinstance(items, list) or not items:
            last_error = "기상청 예보 항목이 비어 있습니다."
            continue

        # 날짜/시간별로 정리
        forecast_by_date: dict[str, dict[str, object]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue

            fcst_date = item.get("fcstDate")
            fcst_time = item.get("fcstTime")
            cat = item.get("category")
            val = item.get("fcstValue")

            dt_key = f"{fcst_date}_{fcst_time}"
            if dt_key not in forecast_by_date:
                forecast_by_date[dt_key] = {}

            if cat == "TMP":
                forecast_by_date[dt_key]["temperature"] = val
            elif cat == "TMN":
                forecast_by_date[dt_key]["daily_min_temp"] = val
            elif cat == "TMX":
                forecast_by_date[dt_key]["daily_max_temp"] = val
            elif cat == "POP":
                forecast_by_date[dt_key]["precipitation_prob"] = val
            elif cat == "WSD":
                forecast_by_date[dt_key]["wind_speed"] = val
            elif cat == "REH":
                forecast_by_date[dt_key]["humidity"] = val
            elif cat == "SKY":
                forecast_by_date[dt_key]["sky"] = val
            elif cat == "PTY":
                forecast_by_date[dt_key]["precipitation_type"] = val

        # 3일치 요약 생성 (최고/최저 기온, 강수 확률 등 묶기)
        daily_summary: dict[str, dict[str, object]] = {}
        for dt_key, fcst in forecast_by_date.items():
            d = dt_key.split("_")[0]
            if d not in daily_summary:
                daily_summary[d] = {
                    "temps": [],
                    "pops": [],
                    "hums": [],
                    "winds": [],
                    "skys": [],
                    "ptys": [],
                    "tmn": None,
                    "tmx": None,
                }

            if "temperature" in fcst:
                try:
                    daily_summary[d]["temps"].append(float(fcst["temperature"]))
                except (TypeError, ValueError):
                    pass
            if "precipitation_prob" in fcst:
                try:
                    daily_summary[d]["pops"].append(int(fcst["precipitation_prob"]))
                except (TypeError, ValueError):
                    pass
            if "wind_speed" in fcst:
                try:
                    daily_summary[d]["winds"].append(float(fcst["wind_speed"]))
                except (TypeError, ValueError):
                    pass
            if "humidity" in fcst:
                try:
                    daily_summary[d]["hums"].append(int(fcst["humidity"]))
                except (TypeError, ValueError):
                    pass
            if "daily_min_temp" in fcst:
                try:
                    raw_min = str(fcst["daily_min_temp"]).replace("℃", "")
                    daily_summary[d]["tmn"] = float(raw_min)
                except (TypeError, ValueError):
                    pass
            if "daily_max_temp" in fcst:
                try:
                    raw_max = str(fcst["daily_max_temp"]).replace("℃", "")
                    daily_summary[d]["tmx"] = float(raw_max)
                except (TypeError, ValueError):
                    pass
            if "sky" in fcst:
                try:
                    daily_summary[d]["skys"].append(int(fcst["sky"]))
                except (TypeError, ValueError):
                    pass
            if "precipitation_type" in fcst:
                try:
                    daily_summary[d]["ptys"].append(int(fcst["precipitation_type"]))
                except (TypeError, ValueError):
                    pass

        formatted_summary = {}
        for d, vals in daily_summary.items():
            temps = vals["temps"]
            pops = vals["pops"]
            winds = vals["winds"]
            skys = vals["skys"]
            ptys = vals["ptys"]

            # 기상청이 제공하는 공식 일최저(TMN)/일최고(TMX)를 우선 사용하고, 없으면 시간별(TMP) 기온에서 추출
            min_t = vals["tmn"] if vals.get("tmn") is not None else (min(temps) if temps else None)
            max_t = vals["tmx"] if vals.get("tmx") is not None else (max(temps) if temps else None)

            max_pty = max(ptys) if ptys else 0
            max_sky = max(skys) if skys else 1
            condition_text = "☀️ 맑음"
            if max_pty > 0:
                if max_pty == 3:
                    condition_text = "❄️ 눈"
                else:
                    condition_text = "🌧️ 비"
            else:
                if max_sky >= 4:
                    condition_text = "☁️ 흐림"
                elif max_sky >= 3:
                    condition_text = "⛅ 구름많음"

            if min_t is not None and max_t is not None:
                formatted_summary[d] = {
                    "min_temp": min_t,
                    "max_temp": max_t,
                    "max_precip_prob": max(pops) if pops else 0,
                    "max_wind_speed": max(winds) if winds else 0.0,
                    "condition": condition_text,
                }

        if formatted_summary:
            w_dict = {
                "daily_forecast": formatted_summary,
                "query_address": region,
                "grid": f"{nx},{ny}",
            }
            weather_cache[region] = (now, w_dict)
            return {"weather_data": w_dict}

        last_error = "기상청 예보 데이터 변환 결과가 비어 있습니다."

    print(f"Weather API Error: {last_error} (region={region}, grid={nx},{ny})")
    return {"weather_data": {"status": "에러", "message": last_error}}

from app.models.ncpms import NcpmsDiagnosis

async def fetch_ncpms(state: DiagnosisState) -> dict:
    pest = state.get("pest", "알 수 없음")
    crop = state.get("crop", "알 수 없음")

    if not pest or pest == "알수없음":
        return {"ncpms_data": "[정보 누락] 해충명이 명확하지 않아 지침을 조회할 수 없습니다."}

    try:
        from app.core.database import async_session
        from sqlalchemy import select
        async with async_session() as db:
            query = select(NcpmsDiagnosis).where(
                NcpmsDiagnosis.pest_name == pest,
                NcpmsDiagnosis.crop_name == crop
            )
            result = await db.execute(query)
            row = result.scalars().first()
            
            if not row:
                fallback_query = select(NcpmsDiagnosis).where(
                    NcpmsDiagnosis.pest_name == pest,
                    NcpmsDiagnosis.crop_name == FALLBACK_CROP_NAME
                )
                result = await db.execute(fallback_query)
                row = result.scalars().first()
                
            if row:
                eco = (row.ecology_info or "").strip()
                prev = (row.prevent_method or "").strip()
                parts = []
                if eco:
                    parts.append(f"### 생태정보\n\n{eco}")
                if prev:
                    parts.append(f"### 방제방법\n\n{prev}")
                md = "\n\n".join(parts) if parts else "데이터 없음"
                return {"ncpms_data": md}
            return {"ncpms_data": f"NCPMS 정보 조회 결과, '{pest}' 및 '{crop}'에 해당하는 데이터를 DB에서 찾을 수 없습니다."}
    except Exception as e:
        return {"ncpms_data": f"NCPMS DB 조회 에러: {str(e)}"}

async def fetch_pesticide(state: DiagnosisState) -> dict:
    pest = state.get("pest", "알 수 없음")
    crop = state.get("crop", "알 수 없음")
    
    try:
        async with async_session() as db:
            query = select(PesticideProduct).where(
                PesticideProduct.target_name.like(f"%{pest}%"),
                PesticideProduct.crop_name.like(f"%{crop}%")
            ).limit(50)
            result = await db.execute(query)
            products = result.scalars().all()
            
            if products:
                # 메모.txt 템플릿에 맞는 grouped_results 형태의 JSON 생성
                grouped = {}
                for p in products:
                    ing_name = p.ingredient_or_formulation_name or "성분정보없음"
                    if ing_name not in grouped:
                        if len(grouped) >= 3: # 최대 3개의 성분만 반환
                            continue
                        grouped[ing_name] = {"ingredient_name": ing_name, "products": []}
                    
                    # 이미 동일한 상표명/제조사의 농약이 있다면 스킵 (중복 제거)
                    is_duplicate = False
                    for existing_prod in grouped[ing_name]["products"]:
                        if existing_prod["brand_name"] == (p.brand_name or "상표명없음"):
                            is_duplicate = True
                            break
                    if is_duplicate:
                        continue
                        
                    if len(grouped[ing_name]["products"]) >= 3: # 한 성분당 최대 3개의 제품만
                        continue
                        
                    grouped[ing_name]["products"].append({
                        "brand_name": p.brand_name or "상표명없음",
                        "corporation_name": p.corporation_name or "제조사없음",
                        "application_method": p.application_method or "정보없음",
                        "application_timing": p.application_timing or "정보없음",
                        "dilution_text": p.dilution_text or "해당 없음 (원액 또는 토양 혼화)",
                        "max_use_count_text": p.max_use_count_text or "정보없음"
                    })
                
                grouped_list = list(grouped.values())
                
                if grouped_list:
                    import json
                    return {"pesticide_data": json.dumps(grouped_list, ensure_ascii=False)}
                else:
                    return {"pesticide_data": "[]"}
            else:
                return {"pesticide_data": "[]"}
    except Exception as e:
        print(f"Pesticide DB Cache error: {e}")
        return {"pesticide_data": "[]"}

async def generate_diagnosis(state: DiagnosisState) -> dict:
    from app.core.config import settings
    api_key = settings.OPENROUTER_API_KEY
    model_name = settings.OPENROUTER_PEST_RAG_MODEL

    # API 키가 없거나 dummy일 경우 목업 데이터 반환
    if api_key == "dummy" or not api_key:
        fallback_json = {
            "result_text": "API 키가 설정되지 않아 가데이터를 출력합니다."
        }
        return {"analysis_result": fallback_json}

    import httpx
    
    # httpx를 통해 HTTP/1.1 강제로 Cloudflare의 HTTP/2 버그(RemoteProtocolError) 원천 차단
    custom_async_client = httpx.AsyncClient(
        http1=True,
        http2=False,
        timeout=httpx.Timeout(180.0, connect=20.0)
    )

    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=settings.OPENROUTER_URL,
        temperature=0.0,
        max_retries=2,
        http_async_client=custom_async_client,
        model_kwargs={"extra_body": {"include_reasoning": False}}
    )

    try:
        weather_info = state.get("weather_data", {})
        if isinstance(weather_info, str):
            weather_info = {}

        weather_summary = _build_weather_unavailable_card("실시간 기상 데이터를 확인할 수 없습니다.")
        weather_for_llm = "데이터 없음"
        daily = weather_info.get("daily_forecast") if isinstance(weather_info, dict) else None
        if isinstance(daily, dict) and daily:
            html_cards = ["<div class='grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 my-3'>"]
            for date_key, td_data in daily.items():
                d_str = f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:]}"
                min_t = td_data['min_temp']
                max_t = td_data['max_temp']
                rain = td_data['max_precip_prob']
                wind = td_data.get('max_wind_speed', 0.0)
                cond = td_data.get('condition', '☀️ 맑음')

                card = f"<div class='bg-blue-50/50 border border-blue-100 rounded-xl p-3 flex flex-col items-center justify-center text-center shadow-sm'><div class='font-bold text-gray-700 mb-1 text-[13px]'>{d_str}</div><div class='font-medium text-blue-800 text-[13px] mb-1'>{cond}</div><div class='text-xl flex flex-col items-center justify-center font-black text-blue-600 mb-1'><span class='text-[10px] font-normal text-gray-500 bg-white px-2 py-0.5 rounded-full shadow-sm mb-1 mt-1'>최저/최고</span><div>{min_t}°<span class='text-gray-400 text-sm font-normal mx-1'>/</span>{max_t}°</div></div><div class='flex flex-col gap-0.5 text-xs text-gray-600 mt-1'><span class='flex items-center justify-center bg-white px-2 py-0.5 rounded border border-blue-100 text-blue-800 font-medium'>☔ 강수 {rain}%</span><span class='flex items-center justify-center bg-white px-2 py-0.5 rounded border border-blue-100 text-blue-800 font-medium'>💨 풍속 {wind}m/s</span></div></div>"
                html_cards.append(card)
            html_cards.append("</div>")
            weather_summary = "".join(html_cards)

            if daily:
                first_day_key = sorted(daily.keys())[0]
                fd = daily[first_day_key]
                temp = f"{fd['min_temp']}~{fd['max_temp']}°C"
                rain = f"{fd['max_precip_prob']}%"
                wind = f"{fd.get('max_wind_speed', 0)}m/s"
                weather_for_llm = f"기온 {temp}, 강수확률 {rain}, 최대풍속 {wind}"
            else:
                weather_for_llm = "데이터 없음"
        else:
            weather_message = ""
            if isinstance(weather_info, dict):
                weather_message = str(weather_info.get("message", "")).strip()
            if weather_message:
                weather_summary = _build_weather_unavailable_card(weather_message)

        try:
            grouped_results = json.loads(state.get("pesticide_data", "[]"))
            if not isinstance(grouped_results, list):
                grouped_results = []
        except Exception:
            grouped_results = []

        pest_html = ""
        for item in grouped_results:
            ing = item.get("ingredient_name", "")
            pest_html += f"<div class='bg-gray-50 border border-gray-200 rounded-xl p-4 my-3'><div class='font-bold text-primary mb-3 text-base flex items-center gap-2'><span>💊</span> 성분: {ing}</div><div class='grid grid-cols-1 md:grid-cols-2 gap-3'>"
            for prod in item.get("products", []):
                bname = prod.get("brand_name", "")
                cname = prod.get("corporation_name", "")
                method = prod.get("application_method", "")
                timing = prod.get("application_timing", "")
                dilution = prod.get("dilution_text", "")
                use_cnt = prod.get("max_use_count_text", "")
                pest_html += f"<div class='bg-white rounded-lg p-3 shadow-none border border-gray-200 flex flex-col h-full'><div class='font-bold text-gray-800 text-sm mb-3 flex items-center flex-wrap gap-2'><span class='text-primary text-[15px]'>{bname}</span><span class='text-[11px] font-normal text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full'>{cname}</span></div><div class='grid grid-cols-2 gap-2 mt-auto'><div class='flex flex-col p-1.5 bg-gray-50/50 rounded'><span class='text-gray-400 mb-0.5 text-[10px]'>사용 방법</span><span class='font-medium text-gray-700 text-xs'>{method}</span></div><div class='flex flex-col p-1.5 bg-gray-50/50 rounded'><span class='text-gray-400 mb-0.5 text-[10px]'>사용 시기</span><span class='font-medium text-gray-700 text-xs'>{timing}</span></div><div class='flex flex-col p-1.5 bg-gray-50/50 rounded'><span class='text-gray-400 mb-0.5 text-[10px]'>희석 배수</span><span class='font-medium text-gray-700 text-xs'>{dilution}</span></div><div class='flex flex-col p-1.5 bg-gray-50/50 rounded'><span class='text-gray-400 mb-0.5 text-[10px]'>사용 횟수</span><span class='font-medium text-gray-700 text-xs'>{use_cnt}</span></div></div></div>"
            pest_html += "</div></div>"
        if not pest_html:
            pest_html = "권장 농약 정보가 없습니다."

        pesticide_summary_text = _summarize_pesticides_for_prompt(grouped_results)

        full_region = state.get("region", "서울")
        parts = full_region.split()
        if len(parts) >= 2:
            display_region = f"{parts[0]} {parts[1]}"
        else:
            display_region = parts[0] if parts else "서울"

        crop_display = state.get("crop") if state.get("crop") else "전체 작물"
        pest_name = state.get("pest", "알 수 없는 해충")
        pest_identification_line = f"🔍 입력하신 이미지는 **{pest_name}**(으)로 인식되었습니다. 이를 기반으로 답변하겠습니다."

        json_payload = {
            "region": display_region,
            "crop_display": crop_display,
            "pest": pest_name,
            "weather_for_llm": weather_for_llm,
            "preventive_info": state.get("ncpms_data") or "데이터 없음",
            "pesticide_summary_text": pesticide_summary_text,
        }
        json_text = json.dumps(json_payload, ensure_ascii=False, indent=2)

        prompt = ChatPromptTemplate.from_messages([
            ("system", """
너는 입력된 JSON 데이터를 보고 AI 요약만 생성하는 농업 전문가다.
반드시 JSON만 출력하라. 추가 설명, 마크다운, HTML, 코드펜스, 플레이스홀더는 출력하지 마라.
출력 형식:
{{
  "weather_advice": "실시간 날씨를 바탕으로 2~3문장 한국어 존댓말로 작성",
  "strategy_bullets": [
    "최적 살포 시기: ...",
    "권장 방제법: ...",
    "재배 관리: ..."
  ]
}}
규칙:
- strategy_bullets는 정확히 3개만 출력한다.
- 각 문장은 짧고 구체적으로 작성한다.
- weather_for_llm, preventive_info, pesticide_summary_text를 참고하여 작성한다.
"""),
            ("user", "{json_text}")
        ])
        chain = prompt | llm | StrOutputParser()

        import asyncio

        max_retries = 3
        raw_response = ""
        for attempt in range(max_retries):
            raw_response = ""
            try:
                async for chunk in chain.astream({"json_text": json_text}):
                    raw_response += chunk
                break
            except Exception as e:
                if "RemoteProtocolError" in str(type(e).__name__) or "ConnectTimeout" in str(type(e).__name__):
                    print(f"LLM streaming dropped connection. Retrying... ({attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2)
                        continue
                raise e

        analysis_notes = _extract_json_object(raw_response) or {}
        weather_advice = _clean_ai_text(str(analysis_notes.get("weather_advice", "")))
        if not weather_advice:
            weather_advice = _build_weather_advice(weather_info)

        raw_strategy_bullets = analysis_notes.get("strategy_bullets", [])
        strategy_bullets: list[str] = []
        if isinstance(raw_strategy_bullets, list):
            for item in raw_strategy_bullets[:3]:
                bullet = _clean_ai_text(str(item)).lstrip("-• ").strip()
                if bullet:
                    strategy_bullets.append(bullet)

        if len(strategy_bullets) < 3:
            fallback_bullets = _build_fallback_strategy_bullets(
                crop_display=crop_display,
                pest=pest_name,
                weather_advice=weather_advice,
            )
            while len(strategy_bullets) < 3:
                strategy_bullets.append(fallback_bullets[len(strategy_bullets)])

        response = _compose_final_response(
            pest_identification_line=pest_identification_line,
            display_region=display_region,
            crop_display=crop_display,
            pest=pest_name,
            pest_html=pest_html,
            preventive_info=state.get("ncpms_data") or "데이터 없음",
            weather_summary=weather_summary,
            weather_advice=weather_advice,
            strategy_bullets=strategy_bullets,
        )

        await custom_async_client.aclose()
        return {"analysis_result": {"result_text": response}}
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"LLM Error: {type(e).__name__} - {e}")
        response = f"AI 엔진 분석 중 오류가 발생했습니다: {type(e).__name__}"
        await custom_async_client.aclose()
        return {"analysis_result": {"result_text": response}}

# Langgraph compilation
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
    """
    이 함수는 더 이상 ainvoke로 한 번에 결과를 반환하지 않고,
    LangGraph의 각 노드 완료마다 상태를 stream(yield) 합니다.
    """
    initial_state = {
        "pest": pest,
        "crop": crop,
        "region": region,
        "weather_data": None,
        "ncpms_data": None,
        "pesticide_data": None,
        "analysis_result": None
    }
    
    async for event in diagnosis_app.astream(initial_state):
        node_name = list(event.keys())[0]
        yield node_name, dict(event[node_name])
