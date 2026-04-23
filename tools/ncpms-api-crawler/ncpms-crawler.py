import os
import json
import time
import requests
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

from defusedxml import ElementTree as ET

# .env 환경변수 로딩 (백엔드 기준 폴더)
env_path = Path(__file__).resolve().parent.parent.parent / "backend" / ".env"
load_dotenv(dotenv_path=env_path)

API_KEY = os.environ.get("NCPMS_API_KEY", "")
BASE_URL = "http://ncpms.rda.go.kr/npmsAPI/service"
REQUEST_DELAY_SECONDS = 0.2
FALLBACK_CROP_NAME = "fallback"
_DETAILS_CACHE: dict[str, dict[str, str]] = {}


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


SESSION = build_session()

# pest_crop_mapping.md 기반 매핑 딕셔너리
PEST_CROP_MAPPINGS = {
    '검거세미밤나방': ['배추'],
    '꽃노랑총채벌레': ['토마토', '콩', '고추'],
    '담배가루이': ['오이', '토마토', '고추'],
    '담배거세미나방': ['콩', '들깨', '고추', '배추'],
    '담배나방': ['고추'],
    '도둑나방': ['배추'],
    '먹노린재': ['벼', '옥수수'],
    '목화바둑명나방': ['오이', '배추'],
    '무잎벌': ['배추'],
    '배추좀나방': ['배추'],
    '배추흰나비': ['배추', '양배추', '고추', '무'],
    '벼룩잎벌레': ['배추', '무', '양배추'],
    '복숭아혹진딧물': ['고추', '토마토', '배추'],
    '비단노린재': ['배추', '양배추'],
    '썩덩나무노린재': ['토마토', '콩'],
    '열대거세미나방': ['옥수수'],
    '큰28점박이무당벌레': ['감자'],
    '톱다리개미허리노린재': ['콩'],
    '파밤나방': ['파', '배추']
}

SYNONYMS = {
    "비단노린재": "홍비단노린재",
    "큰28점박이무당벌레": "큰이십팔점박이무당벌레"
}

def remove_html_tags_from_api_text(raw_html):
    import re

    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.replace('&nbsp;', ' ').strip()


def fetch_api_text(params: dict[str, str]) -> str:
    response = SESSION.get(BASE_URL, params=params, timeout=10)
    response.raise_for_status()
    text = response.text.strip()
    time.sleep(REQUEST_DELAY_SECONDS)
    return text


def fetch_details(insect_key: str) -> dict[str, str]:
    empty_info = {
        "preventMethod": "",
        "ecologyInfo": "",
        "biologyPrvnbeMth": "",
        "chemicalPrvnbeMth": "",
    }
    if not insect_key:
        return empty_info
    if insect_key in _DETAILS_CACHE:
        return _DETAILS_CACHE[insect_key]

    detail_params = {
        "apiKey": API_KEY, "serviceCode": "SVC07", "serviceType": "AA003", "insectKey": insect_key
    }
    try:
        text = fetch_api_text(detail_params)
    except requests.RequestException as exc:
        print(f"상세 API 요청 에러(insectKey={insect_key}): {exc}")
        return empty_info

    info = empty_info.copy()
    
    if text.startswith("{"):
        try:
            data = json.loads(text)
            svc = data.get("service", {})
            info["ecologyInfo"] = remove_html_tags_from_api_text(svc.get("ecologyInfo", ""))
            info["biologyPrvnbeMth"] = remove_html_tags_from_api_text(svc.get("biologyPrvnbeMth", ""))
            info["chemicalPrvnbeMth"] = remove_html_tags_from_api_text(svc.get("chemicalPrvnbeMth", ""))
            info["preventMethod"] = remove_html_tags_from_api_text(svc.get("preventMethod", ""))
        except json.JSONDecodeError as exc:
            print(f"상세 JSON 파싱 실패(insectKey={insect_key}): {exc}")
    else:
        try:
            root = ET.fromstring(text)
            for key in ("ecologyInfo", "biologyPrvnbeMth", "chemicalPrvnbeMth", "preventMethod"):
                val = root.findtext(f".//{key}", "") or ""
                info[key] = remove_html_tags_from_api_text(val)
        except ET.ParseError as exc:
            print(f"상세 XML 파싱 실패(insectKey={insect_key}): {exc}")

    _DETAILS_CACHE[insect_key] = info
    return info

def main():
    if not API_KEY:
        print("ERROR: NCPMS_API_KEY가 설정되지 않았습니다. .env 또는 환경변수를 확인하세요.")
        raise SystemExit(1)

    results = []
    
    for pest, crops in PEST_CROP_MAPPINGS.items():
        official_pest = SYNONYMS.get(pest, pest)
        print(f"[{pest}] 검색 시작 (API명: {official_pest})")
        
        search_params = {
            "apiKey": API_KEY, "serviceCode": "SVC03", "serviceType": "AA003",
            "insectKorName": official_pest, "displayCount": "50"
        }
        
        try:
            text = fetch_api_text(search_params)
        except requests.RequestException as exc:
            print(f"API 요청 에러: {exc}")
            continue
            
        items = []
        if text.startswith("{"):
            try:
                data = json.loads(text)
                items = data.get("service", {}).get("list", [])
                if isinstance(items, dict):
                    items = [items]
                elif not isinstance(items, list):
                    items = []
            except json.JSONDecodeError as exc:
                print(f"검색 JSON 파싱 실패({official_pest}): {exc}")
                continue
        else:
            try:
                root = ET.fromstring(text)
                for item in root.findall(".//item") + root.findall(".//list"):
                    d = {
                        "insectKorName": item.findtext("insectKorName", ""),
                        "cropName": item.findtext("cropName", ""),
                        "insectKey": item.findtext("insectKey", "")
                    }
                    items.append(d)
            except ET.ParseError as exc:
                print(f"검색 XML 파싱 실패({official_pest}): {exc}")
                continue
                
        # API에서 가져온 항목이 없을 경우
        if not items:
            print(f" -> 검색 결과 없음 ({official_pest})")
            continue
            
        # 첫 번째 항목을 Fallback(작물없음) 용으로 추출
        fallback_key = None
        for item in items:
            res_pest = str(item.get("insectKorName", "")).strip()
            if official_pest in res_pest or res_pest in official_pest:
                fallback_key = item.get("insectKey", "")
                break
                
        if fallback_key:
            details = fetch_details(fallback_key)
            results.append({
                "pest_name": pest,
                "crop_name": FALLBACK_CROP_NAME,
                **details
            })
            print(" -> 작물없음(Fallback) 추출 완료")
            
        # 각 타겟 작물별 추출
        for crop in crops:
            best_key = None
            for item in items:
                res_pest = str(item.get("insectKorName", "")).strip()
                res_crop = str(item.get("cropName", "")).strip()
                
                if official_pest in res_pest or res_pest in official_pest:
                    if res_crop and crop in res_crop:
                        best_key = item.get("insectKey", "")
                        break
                        
            # 매칭되는 작물이 없으면 작물없음(Fallback) 키 사용!
            target_key = best_key if best_key else fallback_key
            if target_key:
                details = fetch_details(target_key)
                results.append({
                    "pest_name": pest,
                    "crop_name": crop,
                    **details
                })
                stat = "검색 일치" if best_key else "대체(Fallback)"
                print(f" -> {crop}: {stat} 완료")

    out_file = Path(__file__).resolve().parent / "json_raw" / "ncpms_data.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        
    print(f"\n최종 수집 완료! 총 {len(results)}건 저장됨 -> {out_file}")

if __name__ == "__main__":
    main()
