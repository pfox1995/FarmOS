"""공익직불 규칙 기반 자격 판정.

사용자 프로필 (User 모델 필드)을 바탕으로 각 지원금 프로그램에 대해
deterministic 자격 판정을 수행합니다. 판정 결과:
    - eligible: 모든 기계적 조건 충족. LLM 재확인 없이도 신청 권장 가능.
    - ineligible: 명확히 결격 (예: 경작 면적 0, 경영체 미등록).
    - needs_review: 사용자 프로필만으로는 완전히 판단 불가. 추가 확인 필요.

설계 원칙:
    - 프로그램별 `check_<code>(profile, subsidy)` 함수를 정의
    - 메인 `match_user(profile, subsidies)` 가 각 프로그램별 체커를 호출
    - **법적 책임 경계**: 확실히 결격인 경우만 "ineligible", 조금이라도 불확실하면 "needs_review"
      → 잘못된 "eligible" 판정은 사용자 피해를 유발할 수 있으나, "needs_review" 는 안내 요청으로 끝나므로 안전

예시:
    async with async_session() as db:
        profile = await build_user_profile(db, user_id="farmer01")
        subsidies = (await db.execute(select(Subsidy))).scalars().all()
        result = match_user(profile, subsidies)
        print(result.eligible, result.needs_review, result.ineligible)
"""

from __future__ import annotations

import re

from app.models.subsidy import Subsidy
from app.schemas.subsidy import (
    EligibilityResult,
    MatchResponse,
    PaymentCalculation,
    PaymentStep,
    Reason,
    SourceClause,
    UserProfile,
)


def _short_source(subsidy: Subsidy, suffix: str | None = None) -> str | None:
    """subsidy.source_articles[0] 에서 짧은 조항 태그 추출 (예: "II-3", "II-3 ⑤").

    원문: "CHAPTER 1 II-3 소농직불 지급대상 자격요건"
    반환: "II-3" 또는 suffix 가 주어지면 "II-3 ⑤".

    정규식이 실패하면 전체 문자열을 반환해 UI 에 'Something' 이라도 보이게 한다.
    """
    articles = subsidy.source_articles or []
    if not articles:
        return None
    first = articles[0]
    m = re.search(r"CHAPTER\s+\d+\s+([IVXLCDM]+-\d+)", first)
    base = m.group(1) if m else first
    return f"{base} {suffix}" if suffix else base


# ── 시행지침 소단원 텍스트 카탈로그 ─────────────────────────
# 카탈로그 키는 전체 태그 (예: "II-3 ①") 이어야 서로 다른 조 간 충돌이 없다.
# 연간 시행지침이 갱신되면 여기만 수정하면 된다.

_소농직불_CLAUSES: dict[str, str] = {
    "II-3 ①": "농지 면적 0.1ha ~ 0.5ha (표준 범위). 단, 5천㎡ 이상이면서 면적직불금이 130만원 미만이면 역전구간으로 적용.",
    "II-3 ②": "영농 경력 3년 이상",
    "II-3 ③": "농촌 거주 3년 이상",
    "II-3 ④": "농업경영체 등록 완료 (선결 조건)",
    "II-3 ⑤": "신청자 개인의 농업 외 종합소득이 2,000만원 미만",
    "II-3 ⑥": "농가 구성원 전체의 농업 외 종합소득 합계가 4,500만원 미만",
    "II-3 ⑦": "농가 구성원 전체 경작면적이 15.5천㎡(1.55ha) 미만",
    "II-3 ⑧": "축산업 소득이 5,600만원 미만",
    "II-3 ⑨": "시설재배 소득이 3,800만원 미만",
}

# 면적직불금: 자격 요건은 II-1/II-2, 지급단가는 II-4 에 분산 서술됨.
# seed_data 의 source_articles 는 II-4 만 기록하므로 matcher 에서 직접 태그를 지정한다.
_면적직불_CLAUSES: dict[str, str] = {
    "II-1 ①": "농업경영체 등록 완료",
    "II-1 ②": "대상 농지 유형 (논/밭/과수 등) 일치",
    "II-1 ③": "경작 면적 최소 0.1ha(1천㎡) 이상",
    "II-2 ①": "영농 경력 3년 이상",
    "II-2 ②": "농촌 거주 3년 이상 (신규 신청자 기준)",
    "II-4": "면적·지역 구간별 누진 지급단가 (2ha 이하/2~6ha/6ha 초과 × 진흥/비진흥)",
}


def _collect_source_clauses(
    reasons: list[Reason],
    catalog: dict[str, str],
) -> list[SourceClause]:
    """reasons 에서 참조된 source 태그를 catalog 에서 뽑아 unique 리스트로 반환.

    카탈로그에 없는 태그는 건너뛴다 (hallucinated tag 방지).
    순서는 reasons 등장 순 — UI 에서 가독성 있게 순차 표시.
    """
    seen: set[str] = set()
    out: list[SourceClause] = []
    for r in reasons:
        if not r.source or r.source in seen:
            continue
        text = catalog.get(r.source)
        if text is None:
            continue
        seen.add(r.source)
        out.append(SourceClause(tag=r.source, text=text))
    return out


def _calculate_payment(
    profile: UserProfile, subsidy: Subsidy
) -> PaymentCalculation | None:
    """지급액 계산 내역 (총액 + 단계별 breakdown) 생성.

    fixed: 한 줄 + 면적 무관 설명.
    tiered_by_area: 사용자 프로필 (promotion_area) 에 맞는 tier 선택 후
                    각 면적구간별 계산을 단계로 나열.
    """
    ps = subsidy.payment_structure or {}
    ptype = ps.get("type")

    if ptype == "fixed":
        amount = subsidy.payment_amount_krw or ps.get("amount_krw") or 0
        if amount <= 0:
            return None
        return PaymentCalculation(
            total_krw=amount,
            steps=[PaymentStep(description="정액 지급", amount_krw=amount)],
            note="면적·지역 구간과 무관하게 정액으로 지급됩니다.",
        )

    if ptype != "tiered_by_area":
        return None

    tiers = ps.get("tiers", [])
    matching_tier = next(
        (t for t in tiers if t.get("promotion_area") == profile.is_promotion_area),
        None,
    )
    if not matching_tier:
        return None

    label = matching_tier.get("label", "진흥지역" if profile.is_promotion_area else "비진흥지역")
    steps: list[PaymentStep] = []
    total = 0
    remaining_ha = profile.area_ha
    prev_top_ha = 0.0
    for rng in matching_tier.get("ranges", []):
        hi = rng.get("max_ha")
        rate = rng.get("amount_per_ha", 0)
        if remaining_ha <= 0:
            break
        tier_top = hi if hi is not None else float("inf")
        width = max(tier_top - prev_top_ha, 0.0)
        applicable_ha = min(remaining_ha, width)
        if applicable_ha > 0 and rate > 0:
            step_amount = int(applicable_ha * rate)
            end_label = f"{hi}ha" if hi is not None else "이상"
            steps.append(PaymentStep(
                description=(
                    f"{label} {prev_top_ha:g}~{end_label} 구간: "
                    f"{applicable_ha:g}ha × {rate:,}원/ha"
                ),
                amount_krw=step_amount,
            ))
            total += step_amount
        remaining_ha -= applicable_ha
        prev_top_ha = tier_top

    if total <= 0:
        return None

    return PaymentCalculation(
        total_krw=total,
        steps=steps,
        note=f"{label} 면적 구간별 누진 적용 (시행지침 II-4)",
    )


def _build_result(
    subsidy: Subsidy,
    status: str,
    reasons: list[Reason],
    catalog: dict[str, str] | None = None,
    estimated_amount_krw: int | None = None,
    payment_calculation: PaymentCalculation | None = None,
) -> EligibilityResult:
    """EligibilityResult 팩토리. catalog 가 주어지면 reasons 에서 source_clauses 자동 수집.

    9곳의 early return 에서 중복되던 보일러플레이트를 한 곳으로 모은 헬퍼.
    payment_calculation 이 주어지면 estimated_amount_krw 는 total 에서 자동 도출.
    """
    clauses = _collect_source_clauses(reasons, catalog) if catalog else []
    amount = estimated_amount_krw
    if amount is None and payment_calculation is not None:
        amount = payment_calculation.total_krw
    return EligibilityResult(
        subsidy_code=subsidy.code,
        subsidy_name=subsidy.name_ko,
        status=status,  # type: ignore[arg-type]  # Literal 은 호출부에서 보장
        reasons=reasons,
        estimated_amount_krw=amount,
        source_articles=subsidy.source_articles,
        source_clauses=clauses,
        payment_calculation=payment_calculation,
    )


# ── 프로그램별 자격 판정 함수 ────────────────────────────────


def check_소농직불금(profile: UserProfile, subsidy: Subsidy) -> EligibilityResult:
    """소농직불금 자격 판정 (2026년 기준, 정액 130만원).

    시행지침 II-3 (청크 CH1_S006) + 공식 농림축산식품부 자료 기반.
    8개 자격요건 중:
        [체크 가능]
        ① 농지 면적: 0.1~0.5ha (표준) 또는 5천㎡ 이상+면적직불금<130만원 (역전구간)
        ② 영농 경력 3년 이상
        ③ 농촌 거주 3년 이상
        ④ 농업경영체 등록 (암묵적 선결 조건)
        [체크 불가 — User 모델에 없음]
        ⑤ 개인 농외소득 < 2,000만원
        ⑥ 농가 구성원 합계 농외소득 < 4,500만원
        ⑦ 농가 구성원 전체 경작면적 < 15.5천㎡ (1.55ha)
        ⑧ 축산업 소득 < 5,600만원
        ⑨ 시설재배 소득 < 3,800만원

    설계 원칙 — 비대칭적 리스크 회피:
        거짓 긍정(실제로는 부적격인데 "eligible" 처리) → 부정수급 처벌 위험 (시행지침 II-8)
        거짓 부정(실제로는 적격인데 "ineligible" 처리) → 사용자가 상담원에게 재확인
        ∴ 불확실하면 항상 "needs_review".
        "ineligible"은 체크 가능한 조건이 명확히 실패한 경우에만.

    역전구간 처리:
        - 경작 면적이 0.5ha 이하: 표준 범위 → needs_review
        - 경작 면적이 0.5~1.55ha: 역전구간 가능성 → needs_review + 안내
        - 경작 면적이 1.55ha 초과: 개인 경작만으로도 농가 제한(15.5천㎡) 초과 → ineligible
    """
    AREA_MIN_HA = 0.1
    AREA_STANDARD_MAX_HA = 0.5
    AREA_REVERSAL_MAX_HA = 1.55   # 15.5천㎡ = 1.55ha — 역전구간 포함 상한
    MIN_YEARS = 3

    base_tag = _short_source(subsidy)  # "II-3"

    # 경영체 등록 — 소농직불은 기본직불의 특수 케이스. 등록이 선결조건.
    if not profile.has_farm_registration:
        return _build_result(subsidy, "ineligible", [Reason(
            text="농업경영체 등록이 선결 조건입니다. 먼저 농업경영체 등록을 완료하세요.",
            source=f"{base_tag} ④" if base_tag else None,
        )], catalog=_소농직불_CLAUSES)

    # 최소 면적 미달
    if profile.area_ha < AREA_MIN_HA:
        return _build_result(subsidy, "ineligible", [Reason(
            text=f"경작 면적({profile.area_ha}ha)이 최소 기준 0.1ha(1천㎡)에 미달합니다.",
            source=f"{base_tag} ①" if base_tag else None,
        )], catalog=_소농직불_CLAUSES)

    # 개인 경작 면적만으로도 농가 합계 상한(1.55ha) 초과 — 명확히 불가
    if profile.area_ha > AREA_REVERSAL_MAX_HA:
        return _build_result(subsidy, "ineligible", [
            Reason(
                text=f"경작 면적({profile.area_ha}ha)이 소농직불 대상 범위(1.55ha, 15.5천㎡)를 초과합니다.",
                source=f"{base_tag} ⑦" if base_tag else None,
            ),
            Reason(text="면적직불금 신청을 검토하시기 바랍니다."),
        ], catalog=_소농직불_CLAUSES)

    # 영농 경력 미달
    if profile.years_farming < MIN_YEARS:
        return _build_result(subsidy, "ineligible", [Reason(
            text=f"영농 경력 {MIN_YEARS}년 이상이 필요합니다 (현재 {profile.years_farming}년).",
            source=f"{base_tag} ②" if base_tag else None,
        )], catalog=_소농직불_CLAUSES)

    # 농촌 거주 연수 미달
    if profile.years_rural_residence < MIN_YEARS:
        return _build_result(subsidy, "ineligible", [Reason(
            text=f"농촌 거주 {MIN_YEARS}년 이상이 필요합니다 (현재 {profile.years_rural_residence}년).",
            source=f"{base_tag} ③" if base_tag else None,
        )], catalog=_소농직불_CLAUSES)

    # 여기까지 도달 — 체크 가능한 조건은 모두 충족.
    # 남은 소득·농가 단위 조건은 시스템에서 확인 불가하므로 needs_review.
    # 각 bullet 은 시행지침 II-3 ⑤~⑨ 하위 조항과 1:1 로 매핑된다.
    review_reasons: list[Reason] = [
        Reason(text="기본 요건(경영체 등록, 면적, 영농 3년, 거주 3년)은 충족합니다."),
        Reason(text="다음 항목은 시스템에서 확인할 수 없어 추가 확인이 필요합니다:"),
        Reason(
            text="• 신청자 개인 농업 외 종합소득 2,000만원 미만",
            source=f"{base_tag} ⑤" if base_tag else None,
        ),
        Reason(
            text="• 농가 구성원 전체 농업 외 종합소득 합계 4,500만원 미만",
            source=f"{base_tag} ⑥" if base_tag else None,
        ),
        Reason(
            text="• 농가 구성원 전체 경작면적 15.5천㎡(1.55ha) 미만",
            source=f"{base_tag} ⑦" if base_tag else None,
        ),
        Reason(
            text="• 축산업 소득 5,600만원 미만",
            source=f"{base_tag} ⑧" if base_tag else None,
        ),
        Reason(
            text="• 시설재배 소득 3,800만원 미만",
            source=f"{base_tag} ⑨" if base_tag else None,
        ),
        Reason(text="위 조건까지 모두 충족하시면 연 130만원을 수령하실 수 있습니다."),
    ]

    # 역전구간 안내
    if profile.area_ha > AREA_STANDARD_MAX_HA:
        review_reasons.insert(1, Reason(
            text=(
                f"[참고] 경작 면적({profile.area_ha}ha)은 표준 범위(0.5ha)를 초과하지만, "
                "'역전구간'(5천㎡ 이상이면서 면적직불금이 130만원 미만)에 해당하는 경우 "
                "여전히 소농직불금 신청이 가능합니다."
            ),
            source=f"{base_tag} ①" if base_tag else None,
        ))

    return _build_result(
        subsidy, "needs_review", review_reasons,
        catalog=_소농직불_CLAUSES,
        payment_calculation=_calculate_payment(profile, subsidy),
    )


def check_면적직불금(profile: UserProfile, subsidy: Subsidy) -> EligibilityResult:
    """면적직불금 (논/밭) 자격 판정.

    규칙 (시행지침 II-1, II-4 기준):
        - 농업경영체 등록 필수
        - 농지 면적 ≥ 0.1ha (1천㎡)
        - 농지 유형이 subsidy.eligible_farmland_types 에 포함
        - 영농경력 3년 이상
        - 농촌거주 3년 이상 (신규 신청자)
    """
    # 각 기준별로 (검사 결과, 태그, 실패/성공 문구) 를 수집.
    # 탈락 사유가 하나라도 있으면 ineligible, 아니면 eligible 을 반환한다.
    fail_reasons: list[Reason] = []
    pass_reasons: list[Reason] = []

    # II-1 ① 농업경영체 등록
    if subsidy.requires_farm_registration and not profile.has_farm_registration:
        fail_reasons.append(Reason(
            text="농업경영체 등록이 필요합니다.",
            source="II-1 ①",
        ))
    else:
        pass_reasons.append(Reason(
            text="농업경영체 등록 완료 — 자격 충족",
            source="II-1 ①",
        ))

    # II-1 ② 농지 유형
    eligible_types = subsidy.eligible_farmland_types or []
    if eligible_types and profile.farmland_type and profile.farmland_type not in eligible_types:
        fail_reasons.append(Reason(
            text=(
                f"농지 유형({profile.farmland_type})이 이 지원금 대상이 아닙니다 "
                f"(대상: {', '.join(eligible_types)})."
            ),
            source="II-1 ②",
        ))
    elif profile.farmland_type:
        pass_reasons.append(Reason(
            text=f"대상 농지 유형({profile.farmland_type}) — 자격 충족",
            source="II-1 ②",
        ))

    # II-1 ③ 최소 면적
    if profile.area_ha < subsidy.min_area_ha:
        fail_reasons.append(Reason(
            text=(
                f"경작 면적이 최소 기준({subsidy.min_area_ha}ha) 미만입니다 "
                f"(현재: {profile.area_ha}ha)."
            ),
            source="II-1 ③",
        ))
    else:
        pass_reasons.append(Reason(
            text=(
                f"경작 면적 {profile.area_ha}ha — 자격 충족 "
                f"(최소 {subsidy.min_area_ha}ha 이상)"
            ),
            source="II-1 ③",
        ))

    # II-2 ① 영농 경력
    if profile.years_farming < subsidy.min_farming_years:
        fail_reasons.append(Reason(
            text=(
                f"영농 경력이 최소 기준({subsidy.min_farming_years}년) 미만입니다 "
                f"(현재: {profile.years_farming}년)."
            ),
            source="II-2 ①",
        ))
    else:
        pass_reasons.append(Reason(
            text=(
                f"영농 경력 {profile.years_farming}년 — 자격 충족 "
                f"(최소 {subsidy.min_farming_years}년)"
            ),
            source="II-2 ①",
        ))

    # II-2 ② 농촌 거주
    if profile.years_rural_residence < subsidy.min_rural_residence_years:
        fail_reasons.append(Reason(
            text=(
                f"농촌 거주 연수가 최소 기준({subsidy.min_rural_residence_years}년) 미만입니다 "
                f"(현재: {profile.years_rural_residence}년)."
            ),
            source="II-2 ②",
        ))
    else:
        pass_reasons.append(Reason(
            text=(
                f"농촌 거주 {profile.years_rural_residence}년 — 자격 충족 "
                f"(최소 {subsidy.min_rural_residence_years}년)"
            ),
            source="II-2 ②",
        ))

    if fail_reasons:
        return _build_result(
            subsidy, "ineligible", fail_reasons,
            catalog=_면적직불_CLAUSES,
        )

    # 모든 기준 통과 — 예상 수령액 계산 후 eligible 반환
    calc = _calculate_payment(profile, subsidy)
    pass_reasons.append(Reason(
        text="예상 수령액은 아래 계산 내역을 참고하세요. 실제 지급은 경영체 등록·현장 확인 후 확정됩니다.",
        source="II-4",
    ))
    return _build_result(
        subsidy, "eligible", pass_reasons,
        catalog=_면적직불_CLAUSES,
        payment_calculation=calc,
    )


# ── 메인 라우팅 함수 ────────────────────────────────────────


_CHECKERS = {
    "소농직불금": check_소농직불금,
}


def dispatch_eligibility(profile: UserProfile, subsidy: Subsidy) -> EligibilityResult:
    """지원금 코드로 적절한 체커를 선택하여 판정 결과를 반환.

    Public API — tools.py 및 future deep-agent 가 직접 호출하는 안정 인터페이스.
    """
    checker = _CHECKERS.get(subsidy.code)
    if checker:
        return checker(profile, subsidy)
    # 기본값: 면적직불금 계열은 면적 체커 사용
    if subsidy.code.startswith("면적직불금"):
        return check_면적직불금(profile, subsidy)
    # Fallback — 알 수 없는 프로그램은 needs_review
    return _build_result(subsidy, "needs_review", [Reason(
        text=f"{subsidy.name_ko}에 대한 자동 판정 로직이 없습니다. 상담을 통해 확인하세요.",
    )])


def match_user(profile: UserProfile, subsidies: list[Subsidy]) -> MatchResponse:
    """모든 지원금에 대해 자격 판정을 수행하고 결과를 분류한다."""
    eligible: list[EligibilityResult] = []
    ineligible: list[EligibilityResult] = []
    review: list[EligibilityResult] = []

    for sub in subsidies:
        if not sub.is_active:
            continue
        result = dispatch_eligibility(profile, sub)
        if result.status == "eligible":
            eligible.append(result)
        elif result.status == "ineligible":
            ineligible.append(result)
        else:
            review.append(result)

    return MatchResponse(
        user_id=profile.user_id,
        eligible=eligible,
        ineligible=ineligible,
        needs_review=review,
    )
