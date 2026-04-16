import os
import time
import json
import re
from typing import TypedDict, Optional
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

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

async def fetch_weather(state: DiagnosisState) -> dict:
    region = state.get("region", "서울")
    
    # region_name -> KMA Coordinates 매핑
    mapping = {
        "서울": ("60", "127"), "인천": ("55", "124"), "대전": ("67", "100"),
        "대구": ("89", "90"), "광주": ("58", "74"), "부산": ("98", "76"),
        "울산": ("102", "84"), "세종": ("66", "103"), "경기": ("60", "120"),
        "강원": ("73", "134"), "충북": ("69", "107"), "충남": ("68", "100"),
        "전북": ("63", "89"), "전남": ("58", "74"),  "경북": ("89", "90"),
        "경남": ("91", "77"), "제주": ("52", "38")
    }
    
    nx, ny = "60", "127"
    for key, coords in mapping.items():
        if key in region:
            nx, ny = coords
            break
            
    now = time.time()
    if region in weather_cache:
        cached_time, cached_data = weather_cache[region]
        if now - cached_time < WEATHER_CACHE_TTL:
            return {"weather_data": cached_data}
            
    api_key = os.getenv("WEATHER_API_KEY")
    if not api_key:
        return {"weather_data": {"temperature": "에러", "humidity": "-", "wind_speed": "-", "precipitation_prob": "-"}}

    import requests
    from datetime import datetime, timedelta
    current_time = datetime.now()
    target = current_time - timedelta(hours=3, minutes=10)
    
    url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
    params = {
        "serviceKey": api_key, "pageNo": "1", "numOfRows": "100", "dataType": "JSON", 
        "base_date": target.strftime("%Y%m%d"), 
        "base_time": f"{(target.hour // 3) * 3 + 2:02d}00", 
        "nx": nx, "ny": ny
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
            weather_dict = {}
            for item in items:
                cat, val = item.get('category'), item.get('fcstValue')
                if cat == 'TMP' and 'temperature' not in weather_dict: weather_dict['temperature'] = val
                if cat == 'POP' and 'precipitation_prob' not in weather_dict: weather_dict['precipitation_prob'] = val
                if cat == 'REH' and 'humidity' not in weather_dict: weather_dict['humidity'] = val
                if cat == 'WSD' and 'wind_speed' not in weather_dict: weather_dict['wind_speed'] = val
            
            w_str = f"{weather_dict.get('temperature', '-')}℃, {weather_dict.get('humidity', '-')}%, {weather_dict.get('wind_speed', '-')}m/s, {weather_dict.get('precipitation_prob', '-')}%"
            weather_cache[region] = (now, weather_dict)
            return {"weather_data": weather_dict}
        return {"weather_data": {"temperature": "-", "humidity": "-", "wind_speed": "-", "precipitation_prob": "-"}}
    except Exception as e:
        return {"weather_data": {"temperature": "-", "humidity": "-", "wind_speed": "-", "precipitation_prob": "-"}}

async def fetch_ncpms(state: DiagnosisState) -> dict:
    pest = state.get("pest", "알 수 없음")
    crop = state.get("crop", "알 수 없음")
    
    if not pest or pest == "알수없음": 
        return {"ncpms_data": "[정보 누락] 해충명이 명확하지 않아 지침을 조회할 수 없습니다."}
        
    synonyms = {
        "비단노린재": "홍비단노린재",
        "큰28점박이무당벌레": "큰이십팔점박이무당벌레"
    }
    official_pest_name = synonyms.get(pest, pest)
    
    cache_key = official_pest_name
    now = time.time()
    
    if cache_key in ncpms_cache:
        cached_time, cached_data = ncpms_cache[cache_key]
        if now - cached_time < NCPMS_CACHE_TTL:
            return {"ncpms_data": cached_data}

    api_key = os.getenv("NCPMS_API_KEY")
    if not api_key: 
        return {"ncpms_data": "NCPMS API 키(`NCPMS_API_KEY`)가 설정되지 않았습니다."}

    import requests
    import xml.etree.ElementTree as ET
    import re
    
    try:
        base_url = "http://ncpms.rda.go.kr/npmsAPI/service"
        search_params = {
            "apiKey": api_key, 
            "serviceCode": "SVC03", 
            "serviceType": "AA003", 
            "insectKorName": official_pest_name,
            "displayCount": "50"
        }
        search_resp = requests.get(base_url, params=search_params, timeout=10)
        text_resp = search_resp.text.strip()
        
        best_key = None
        fallback_key = None
        
        if text_resp.startswith("{"):
            data = json.loads(text_resp)
            service_data = data.get("service", {})
            if "returnAuthMsg" in service_data and service_data["returnAuthMsg"] not in ["NORMAL SERVICE.", "NORMAL SERVICE"]:
                return {"ncpms_data": f"API 인증 실패: {service_data['returnAuthMsg']}"}
                
            items = service_data.get("list", [])
            if isinstance(items, dict):
                items = [items]
                
            for item in items:
                res_pest = str(item.get("insectKorName", "")).strip()
                res_crop = str(item.get("cropName", "")).strip()
                insect_key = str(item.get("insectKey", ""))
                
                if res_pest and (official_pest_name in res_pest or res_pest in official_pest_name):
                    if not fallback_key:
                        fallback_key = insect_key
                    if crop and res_crop and crop in res_crop:
                        best_key = insect_key
                        break
        else:
            root = ET.fromstring(text_resp)
            for item in root.findall(".//item") + root.findall(".//list"):
                res_pest = item.findtext("insectKorName", "").strip()
                res_crop = item.findtext("cropName", "").strip()
                insect_key = item.findtext("insectKey", "")
                
                if res_pest and (official_pest_name in res_pest or res_pest in official_pest_name):
                    if not fallback_key:
                        fallback_key = insect_key
                    if crop and res_crop and crop in res_crop:
                        best_key = insect_key
                        break

        final_key = best_key or fallback_key
        if not final_key:
            return {"ncpms_data": f"NCPMS 정보 조회 결과, '{official_pest_name}'에 해당하는 데이터를 찾을 수 없습니다."}

        detail_params = {
            "apiKey": api_key, "serviceCode": "SVC07", "serviceType": "AA003", "insectKey": final_key
        }
        detail_resp = requests.get(base_url, params=detail_params, timeout=10)
        detail_text = detail_resp.text.strip()
        
        prevent_method, ecology_info, biology_method = "", "", ""
        if detail_text.startswith("{"):
            detail_data = json.loads(detail_text)
            service_data = detail_data.get("service", {})
            item = service_data
            if "list" in service_data:
                list_data = service_data["list"]
                if isinstance(list_data, list) and len(list_data) > 0:
                    item = list_data[0]
                elif isinstance(list_data, dict):
                    item = list_data
            prevent_method = item.get("preventMethod", "")
            ecology_info = item.get("ecologyInfo", "")
            biology_method = item.get("biologyPrvnbeMth", "")
        else:
            detail_tree = ET.fromstring(detail_resp.content)
            prevent_method = detail_tree.findtext(".//preventMethod", default="").strip()
            ecology_info = detail_tree.findtext(".//ecologyInfo", default="").strip()
            biology_method = detail_tree.findtext(".//biologyPrvnbeMth", default="").strip()
            
        def improve_readability(text: str) -> str:
            if not text: return ""
            text = text.replace(".", ". ")
            text = text.replace("~", "～")
            text = re.sub(r'\s+', ' ', text)
            return text.strip()
        
        info_parts = []
        if prevent_method:
            info_parts.append(f"### 재배 및 물리적 방제\n\n{improve_readability(prevent_method)}")
        if ecology_info:
            info_parts.append(f"### 생태 환경\n\n{improve_readability(ecology_info)}")
        if biology_method:
            info_parts.append(f"### 생물학적 방제\n\n{improve_readability(biology_method)}")
        
        html_tag_re = re.compile(r'<[^>]+>')
        final_info = "\n\n".join(info_parts)
        final_info = html_tag_re.sub('', final_info).replace("&nbsp;", " ").replace("&gt;", ">").replace("&lt;", "<").strip()
        
        if final_info:
            ncpms_cache[cache_key] = (now, final_info)
            return {"ncpms_data": final_info}
        
        return {"ncpms_data": "NCPMS 응답에서 방제 지침 정보를 찾을 수 없습니다. (데이터 없음)"}

    except Exception as e:
        return {"ncpms_data": f"NCPMS 통신 에러: {str(e)}"}

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
    api_key = os.getenv("OPENROUTER_API_KEY", "dummy_key")
    model_name = os.getenv("OPENROUTER_PEST_RAG_MODEL", "openai/gpt-5-nano")
    
    # API 키가 없거나 dummy일 경우 목업 데이터 반환
    if api_key == "dummy_key" or not api_key:
        fallback_json = {
            "result_text": "API 키가 설정되지 않아 가데이터를 출력합니다."
        }
        return {"analysis_result": fallback_json}

    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        temperature=0.0
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", """
너는 입력된 JSON 데이터를 정해진 텍스트 템플릿에 매핑하는 '템플릿 엔진(Template Engine)'이다.
절대 스스로 생각해서 문장을 지어내거나 단어, 줄바꿈을 임의로 바꾸지 마라.

[과거 대화 내역]
{history}

[입력 데이터]
{json_text}
질문: {user_question}

==================================================
🚨 [작동 모드 판단 규칙]
1. 입력 데이터(JSON)에 "grouped_results"가 존재하면 -> <모드 A> 실행
2. 입력 데이터가 비어있거나, 일반적인 농업/약제 관련 질문이면 -> <모드 B> 실행

▶ <모드 A: 템플릿 엔진 모드 (엄격한 데이터 치환)>
아래 [출력 템플릿]의 텍스트와 빈 줄을 100% 그대로 복사하되, `[[ ]]` 안의 값만 JSON 데이터로 치환한다.

* 절대 규칙 1 (원문 100% 보존): JSON의 텍스트를 임의로 수정/편집하지 마라. (예: preventive_info 본문의 빈 줄을 없애거나 ■ 기호를 함부로 추가하지 마라. 단어를 바꾸지 마라). 반드시 원본 문자열 그대로 붙여넣어라.
* 절대 규칙 2 (농약 그룹화): grouped_results를 순회할 때 `- 성분/제형: [[ingredient_name]]`은 딱 한 번만 적고, 그 아래에 제품 목록을 들여쓰기와 마크다운 리스트 형식(`- `)에 맞춰 나열해라.
* 절대 규칙 3 (사족 및 훼손 금지): 출력물의 앞뒤에 설명, 인사말을 절대 넣지 마라. 결과물은 반드시 제공된 마크다운 템플릿(헤더 `##`, 리스트 `- ` 등)을 그대로 유지해야 한다.
* 절대 규칙 4: 치환이 끝난 후 `[[ ]]` 기호는 출력물에서 완벽히 삭제한다.
* 절대 규칙 5 (추가 정보 금지): "## ⚠️ 공지:" 섹션으로 출력이 반드시 끝나야 한다. 그 뒤에 "그 밖의 정보", "참고", "추가 데이터", "grouped_results", JSON 덩어리 등 어떤 형태로든 내용을 더 붙이지 마라. 원본 JSON 데이터를 통째로 출력하지 마라.

▶ <모드 B: 일반 대화 모드>
템플릿을 완전히 무시하고, 사용자의 질문에 친절하고 상세한 농업 전문가로서 직접 대답한다.
==================================================

[모드 A 완벽 처리 예시] - 반드시 이 예시의 패턴을 100% 모방하여 답변해라.
(랭플로우 에러 방지를 위해 괄호를 생략한 데이터 구조)
입력 데이터:
"region": "서울", "crop_display": "배추", "pest": "벼룩잎벌레"
"preventive_info": "### 재배 및 물리적 방제\\n\\n이 해충의 유충은 땅속에서 경과하고..."
"temp": "25", "humi": "50", "wind": "1.2", "rain": "0"
"grouped_results" 내부의 "ingredient_name": "다이아지논 입제"
그 내부 "products"의 "brand_name": "듀크", "corporation_name": "성보화학(주)", "application_method": "파종 또는 이식전", "application_timing": "파종정식전", "dilution_text": "해당 없음 (원액 또는 토양 혼화)", "max_use_count_text": "1회 이내"

출력 결과물 (마크다운 형식 적용, ## ⚠️ 공지 섹션으로 끝남):
## 🌿 서울 지역의 배추 벼룩잎벌레 방제 솔루션입니다.

## 🧪 권장 농약 목록 (출처: 농촌진흥청 농약안전정보시스템)

- 성분/제형: 다이아지논 입제
  - 듀크 [ 성보화학(주) ]
    - 사용 방법: 파종 또는 이식전
    - 사용 시기: 파종정식전
    - 희석 배수: 해당 없음 (원액 또는 토양 혼화)
    - 사용 횟수: 1회 이내

## 🚜 객관적 예방 및 재배적 방제 지침 (출처: 국가농작물병해충관리시스템 NCPMS)

### 재배 및 물리적 방제

이 해충의 유충은 땅속에서 경과하고...

## 💡 실시간 환경 맞춤 조언 (출처: 기상청 단기예보 서비스)

- 현재 날씨: 25℃, 50%, 1.2 m/s, 0%
- 조언: 바람이 약하고 비가 없어 살포에 적합한 조건입니다.

## ⚠️ 공지: 제공된 정보는 공공데이터에 기반한 참고용입니다. 농약 사용 전 반드시 제품 라벨의 규정을 확인하십시오.

[주의: 위 "## ⚠️ 공지" 섹션 이후에는 절대로 아무런 텍스트, JSON 데이터, "grouped_results", "그 밖의 정보" 등을 출력하지 마라. 출력이 여기서 완전히 끝나야 한다.]
==================================================

[출력 템플릿] (※ 주의: 이 줄과 아래 점선은 절대 출력하지 마라)
## 🌿 [[region]] 지역의 [[crop_display]] [[pest]] 방제 솔루션입니다.

## 🧪 권장 농약 목록 (출처: 농촌진흥청 농약안전정보시스템)

- 성분/제형: [[ingredient_name]]
  - [[brand_name]] [ [[corporation_name]] ]
    - 사용 방법: [[application_method]]
    - 사용 시기: [[application_timing]]
    - 희석 배수: [[dilution_text]]
    - 사용 횟수: [[max_use_count_text]]

## 🚜 객관적 예방 및 재배적 방제 지침 (출처: 국가농작물병해충관리시스템 NCPMS)

[[preventive_info]]

## 💡 실시간 환경 맞춤 조언 (출처: 기상청 단기예보 서비스)

- 현재 날씨: [[temp]]℃, [[humi]]%, [[wind]] m/s, [[rain]]%
- 조언: [[날씨 데이터를 바탕으로 한 살포 조언을 1문장으로 작성]]

## ⚠️ 공지: 제공된 정보는 공공데이터에 기반한 참고용입니다. 농약 사용 전 반드시 제품 라벨의 규정을 확인하십시오.
--------------------------------------------------
"""),
        ("user", "데이터를 기반으로 템플릿 엔진의 역할을 수행하라.")
    ])

    from langchain_core.output_parsers import StrOutputParser
    chain = prompt | llm | StrOutputParser()
    
    import json
    
    try:
        weather_info = state.get("weather_data", {})
        if isinstance(weather_info, str):
            weather_info = {}

        # 날씨 필드명 통일 (랭플로우와 동일하게)
        temp = str(weather_info.get("temperature", "데이터 없음"))
        humi = str(weather_info.get("humidity", "데이터 없음"))
        wind = str(weather_info.get("wind_speed", "데이터 없음"))
        rain = str(weather_info.get("precipitation_prob", "데이터 없음"))
        
        try:
            grouped_results = json.loads(state.get("pesticide_data", "[]"))
        except:
            grouped_results = []

        json_payload = {
            "region": state.get("region"),
            "crop_display": state.get("crop") if state.get("crop") else "전체 작물",
            "pest": state.get("pest"),
            "temp": temp,
            "humi": humi,
            "wind": wind,
            "rain": rain,
            "preventive_info": state.get("ncpms_data") or "데이터 없음",
            "grouped_results": grouped_results
        }
        
        json_text = json.dumps(json_payload, ensure_ascii=False)

        raw_response = await chain.ainvoke({
            "history": "과거 대화 내역 없음",
            "user_question": f"{state.get('crop')} {state.get('pest')} 방제 방법 알려줘",
            "json_text": json_text
        })
        # Remove any unfilled brackets if left behind
        response = re.sub(r'\[\[.*?\]\]', '', raw_response)
        
        # 'grouped_results' 같은 JSON 잔재가 환각으로 출력되었을 경우 잘라내기
        if "## ⚠️ 공지" in response:
            parts = response.split("## ⚠️ 공지")
            response = parts[0] + "## ⚠️ 공지" + parts[1].split("\n")[0]
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"LLM Error: {type(e).__name__} - {e}")
        response = f"AI 엔진 분석 중 오류가 발생했습니다: {type(e).__name__}"

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

async def run_diagnosis(pest: str, crop: str, region: str) -> dict:
    initial_state = {
        "pest": pest,
        "crop": crop,
        "region": region,
        "weather_data": None,
        "ncpms_data": None,
        "pesticide_data": None,
        "analysis_result": None
    }
    result = await diagnosis_app.ainvoke(initial_state)
    return result["analysis_result"]
