"""영농일지 STT 텍스트 파서 — OpenRouter + Gemma 4 31B 기반."""

import json
from datetime import date, timedelta

import httpx

from app.core.config import settings

SYSTEM_PROMPT = """당신은 한국어 영농일지 음성 텍스트를 구조화된 JSON으로 변환하는 파서입니다.

입력: 농부가 음성으로 말한 영농 작업 내용 (비정형 한국어 텍스트)
출력: 아래 필드를 가진 JSON 객체 (해당 없는 필드는 null)

필드 목록:
- work_date: 작업일 (YYYY-MM-DD 형식, "오늘"이면 {today}, "어제"이면 {yesterday})
- field_name: 필지 (예: "1번 필지", "하우스 2호", "A동")
- crop: 작목 (예: "사과", "고추", "토마토", "딸기", "배", "포도", "벼", "감자")
- work_stage: 작업단계 (반드시 다음 중 하나: 사전준비, 경운, 파종, 정식, 작물관리, 수확)
  - 약제 살포, 방제, 비료 주기, 봉지 씌우기, 적과, 전정 등은 모두 "작물관리"
  - 밭 갈기, 로타리 등은 "경운"
  - 씨 뿌리기는 "파종"
  - 모종 심기는 "정식"
  - 따기, 캐기, 베기 등은 "수확"
  - 자재 준비, 기계 점검 등은 "사전준비"
- weather: 날씨 (맑음, 흐림, 비, 눈 등. 언급 없으면 null)
- disease: 병해충명 (예: "진딧물", "녹병", "탄저병", "역병". 언급 없으면 null)
- usage_pesticide_product: 사용한 농약 제품명 (예: "프로피네브 수화제", "모스피란")
- usage_pesticide_amount: 농약 사용량 (예: "500배액", "1리터", "1000배")
- usage_fertilizer_product: 사용한 비료 제품명 (예: "요소비료", "복합비료")
- usage_fertilizer_amount: 비료 사용량 (예: "10kg", "두 포대")
- detail: 입력 텍스트의 핵심 내용을 영농일지 세부작업내용으로 한 문장으로 정리 (이 필드는 절대 null로 두지 마세요)

반드시 JSON만 출력하세요. 설명이나 마크다운 없이 순수 JSON만 출력합니다.
work_date, field_name, crop 등 위 필드에서 언급되지 않은 정보는 null로 두되, detail은 반드시 작성하세요."""


def _build_system_prompt() -> str:
    """오늘/어제 날짜를 프롬프트에 삽입."""
    today = date.today()
    yesterday = today - timedelta(days=1)
    return SYSTEM_PROMPT.format(
        today=today.isoformat(),
        yesterday=yesterday.isoformat(),
    )


def _extract_json(text: str) -> dict | None:
    """LLM 응답에서 JSON 추출."""
    text = text.strip()
    # ```json ... ``` 블록 처리
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                try:
                    return json.loads(part)
                except json.JSONDecodeError:
                    continue
    # 직접 파싱
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                return None
    return None


VALID_STAGES = {"사전준비", "경운", "파종", "정식", "작물관리", "수확"}

PARSED_FIELDS = [
    "work_date",
    "field_name",
    "crop",
    "work_stage",
    "weather",
    "disease",
    "usage_pesticide_product",
    "usage_pesticide_amount",
    "usage_fertilizer_product",
    "usage_fertilizer_amount",
    "detail",
]


def _validate_and_clean(parsed: dict) -> dict:
    """파싱 결과를 검증하고 정리."""
    # work_stage 유효성 검사
    stage = parsed.get("work_stage")
    if stage and stage not in VALID_STAGES:
        # 부분 매칭 시도
        for valid in VALID_STAGES:
            if valid in stage or stage in valid:
                parsed["work_stage"] = valid
                break
        else:
            parsed["work_stage"] = None

    # null 문자열 → None 변환
    for key in PARSED_FIELDS:
        val = parsed.get(key)
        if val is not None and str(val).strip().lower() in ("null", "none", ""):
            parsed[key] = None

    return parsed


def _compute_confidence(parsed: dict, raw_text: str) -> dict:
    """필드별 신뢰도 추정. 원문에 해당 값이 포함되어 있으면 높은 신뢰도."""
    confidence = {}
    for field in PARSED_FIELDS:
        val = parsed.get(field)
        if val is None:
            continue
        val_str = str(val)
        if val_str in raw_text:
            confidence[field] = 1.0
        elif any(part in raw_text for part in val_str.split() if len(part) > 1):
            confidence[field] = 0.8
        else:
            confidence[field] = 0.5
    return confidence


def _compute_unparsed(parsed: dict, raw_text: str) -> str:
    """파싱된 값을 제거한 나머지 텍스트."""
    remaining = raw_text
    for field in PARSED_FIELDS:
        val = parsed.get(field)
        if val is not None:
            remaining = remaining.replace(str(val), "")
    # 정리
    remaining = " ".join(remaining.split()).strip()
    return remaining


async def parse_stt_text(raw_text: str) -> dict:
    """STT 텍스트를 OpenRouter LLM으로 구조화.

    Returns:
        {"parsed": {...}, "confidence": {...}, "unparsed_text": "..."}
    """
    url = f"{settings.OPENROUTER_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"}
    payload = {
        "model": settings.OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": _build_system_prompt()},
            {"role": "user", "content": raw_text},
        ],
        "temperature": 0.1,
        "max_tokens": 2048,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()

    data = resp.json()
    response_text = data["choices"][0]["message"]["content"] or ""
    parsed = _extract_json(response_text)

    if parsed is None:
        return {
            "parsed": {},
            "confidence": {},
            "unparsed_text": raw_text,
        }

    parsed = _validate_and_clean(parsed)
    confidence = _compute_confidence(parsed, raw_text)
    unparsed = _compute_unparsed(parsed, raw_text)

    # parsed에서 None 값 제거 (응답 깔끔하게)
    clean_parsed = {
        k: v for k, v in parsed.items() if v is not None and k in PARSED_FIELDS
    }

    return {
        "parsed": clean_parsed,
        "confidence": confidence,
        "unparsed_text": unparsed,
    }
