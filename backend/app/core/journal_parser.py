"""영농일지 STT 텍스트 파서 — OpenRouter + Gemma 4 31B 기반."""

import json
from datetime import date, timedelta

import httpx

from app.core.config import settings

SYSTEM_PROMPT = """당신은 한국어 영농일지 음성 텍스트를 구조화된 JSON으로 변환하는 파서입니다.

입력: 농부가 음성으로 말한 영농 작업 내용 (비정형 한국어 텍스트)
출력: **JSON 배열** — 작업 단위로 분리된 객체들의 리스트

중요: 한 발화에 여러 작업이 섞여 있으면 (예: "1번 필지에는 방제하고, 2번 필지에서는 수확했어")
각 작업을 **별도 객체로 분리**해 배열에 담으세요. 단일 작업이면 길이 1 배열을 반환합니다.

각 객체의 필드 (해당 없는 필드는 null):

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
- detail: 입력 텍스트의 핵심 내용을 영농일지 세부작업내용으로 한 문장으로 정리

거절 규칙:
- 입력 전체가 영농 작업과 무관한 일상 대화, 잡담, 시스템/앱 관련 언급, 잡음 전사 등이라면
  배열 대신 다음 형태의 객체를 반환하세요:
  {{"rejected": true, "reject_reason": "<짧은 사유>"}}
- 영농 관련 내용이 조금이라도 있으면 거절하지 말고 가능한 만큼 배열에 담으세요.

반드시 JSON만 출력하세요. 설명이나 마크다운 없이 순수 JSON만 출력합니다.
기본 출력 형식은 **배열** `[{{...}}, {{...}}]` 입니다. 거절 시에만 객체를 반환합니다."""


def _build_system_prompt() -> str:
    """오늘/어제 날짜를 프롬프트에 삽입."""
    today = date.today()
    yesterday = today - timedelta(days=1)
    return SYSTEM_PROMPT.format(
        today=today.isoformat(),
        yesterday=yesterday.isoformat(),
    )


def _extract_json(text: str):
    """LLM 응답에서 JSON 추출. 배열 또는 객체 반환 가능."""
    text = text.strip()
    # ```json ... ``` 블록 처리
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("[") or part.startswith("{"):
                try:
                    return json.loads(part)
                except json.JSONDecodeError:
                    continue
    # 직접 파싱
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 배열 우선 탐색
    for open_ch, close_ch in (("[", "]"), ("{", "}")):
        start = text.find(open_ch)
        end = text.rfind(close_ch) + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                continue
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
    extracted = _extract_json(response_text)

    if extracted is None:
        return {
            "entries": [],
            "unparsed_text": raw_text,
            "rejected": True,
            "reject_reason": "응답 파싱 실패",
        }

    # 거절 케이스: 객체 형태이고 rejected=True
    if isinstance(extracted, dict) and extracted.get("rejected"):
        return {
            "entries": [],
            "unparsed_text": raw_text,
            "rejected": True,
            "reject_reason": extracted.get("reject_reason")
            or "영농 작업 내용을 찾지 못했습니다.",
        }

    # 하위 호환: 객체 하나만 온 경우 배열로 감싸기
    if isinstance(extracted, dict):
        extracted = [extracted]

    if not isinstance(extracted, list):
        return {
            "entries": [],
            "unparsed_text": raw_text,
            "rejected": True,
            "reject_reason": "응답 형식 오류",
        }

    reject_kws = ("관련 없", "추출할 수 없", "판단되어", "확인되지 않")
    entries: list[dict] = []
    for item in extracted:
        if not isinstance(item, dict):
            continue
        parsed = _validate_and_clean(item)

        # entry-level 거절 감지 (안전망)
        meaningful = any(parsed.get(k) for k in PARSED_FIELDS if k != "detail")
        detail_val = (parsed.get("detail") or "").strip()
        if not meaningful and detail_val and any(kw in detail_val for kw in reject_kws):
            continue

        confidence = _compute_confidence(parsed, raw_text)
        clean_parsed = {
            k: v for k, v in parsed.items() if v is not None and k in PARSED_FIELDS
        }
        if not clean_parsed:
            continue
        entries.append({"parsed": clean_parsed, "confidence": confidence})

    if not entries:
        return {
            "entries": [],
            "unparsed_text": raw_text,
            "rejected": True,
            "reject_reason": "영농 작업 내용을 찾지 못했습니다.",
        }

    return {
        "entries": entries,
        "unparsed_text": "",
        "rejected": False,
    }
