"""농약 제품명 매칭 — LLM 파싱 결과를 농약 DB와 대조하여 보정."""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pesticide import PesticideProduct


def _pick_best(products: list[PesticideProduct], confidence: float) -> dict:
    """여러 매칭 결과 중 대표 1건 선택 (제품명이 짧은 것 우선)."""
    p = min(products, key=lambda x: len(x.ingredient_or_formulation_name or ""))
    return {
        "matched_name": p.ingredient_or_formulation_name,
        "brand": p.brand_name,
        "company": p.corporation_name,
        "purpose": p.usage_purpose_name,
        "crop": p.crop_name,
        "confidence": confidence,
    }


async def match_pesticide(
    db: AsyncSession,
    raw_name: str,
    crop: str | None = None,
    disease: str | None = None,
) -> dict | None:
    """LLM이 파싱한 농약명을 DB에서 매칭.

    crop/disease가 주어지면 해당 조건에 등록된 농약 우선 매칭.

    매칭 우선순위:
      1. 작물 + 병해충 필터
      2. 작물 필터만
      3. 필터 없이 전체 검색

    Returns:
        {"matched_name", "brand", "company", "purpose", "crop", "confidence"} or None
    """
    if not raw_name or not raw_name.strip():
        return None

    raw_name = raw_name.strip()

    # 필터 조합: 좁은 범위 → 넓은 범위
    filter_combos = []
    if crop and disease:
        filter_combos.append((crop.strip(), disease.strip()))
    if crop:
        filter_combos.append((crop.strip(), None))
    filter_combos.append((None, None))

    for crop_f, disease_f in filter_combos:
        result = await _search(db, raw_name, crop_f, disease_f)
        if result:
            return result

    return None


async def _search(
    db: AsyncSession,
    raw_name: str,
    crop_filter: str | None,
    disease_filter: str | None = None,
) -> dict | None:
    """단일 검색 라운드 (작물/병해충 필터 적용/미적용)."""

    def _apply_filters(stmt):
        if crop_filter:
            stmt = stmt.where(PesticideProduct.crop_name == crop_filter)
        if disease_filter:
            stmt = stmt.where(
                PesticideProduct.target_name.ilike(f"%{disease_filter}%")
            )
        return stmt

    # 1순위: 제품명 정확 매칭
    stmt = select(PesticideProduct).where(
        PesticideProduct.ingredient_or_formulation_name == raw_name
    )
    stmt = _apply_filters(stmt)
    result = await db.execute(stmt)
    products = result.scalars().all()
    if products:
        conf = 1.0 if (crop_filter and disease_filter) else 0.95 if crop_filter else 0.9
        return _pick_best(products, conf)

    # 2순위: 브랜드명 정확 매칭
    stmt = select(PesticideProduct).where(PesticideProduct.brand_name == raw_name)
    stmt = _apply_filters(stmt)
    result = await db.execute(stmt)
    products = result.scalars().all()
    if products:
        conf = (
            0.95 if (crop_filter and disease_filter) else 0.9 if crop_filter else 0.85
        )
        return _pick_best(products, conf)

    # 3순위: 제품명 또는 브랜드명 부분 매칭
    stmt = select(PesticideProduct).where(
        or_(
            PesticideProduct.ingredient_or_formulation_name.ilike(f"%{raw_name}%"),
            PesticideProduct.brand_name.ilike(f"%{raw_name}%"),
        )
    )
    stmt = _apply_filters(stmt)
    result = await db.execute(stmt)
    products = result.scalars().all()
    if products:
        conf = 0.85 if (crop_filter or disease_filter) else 0.7
        return _pick_best(products, conf)

    # 4순위: 토큰 매칭 (단어 분리 후 가장 긴 토큰)
    tokens = [t for t in raw_name.split() if len(t) >= 2]
    tokens.sort(key=len, reverse=True)

    for token in tokens:
        stmt = select(PesticideProduct).where(
            or_(
                PesticideProduct.ingredient_or_formulation_name.ilike(f"%{token}%"),
                PesticideProduct.brand_name.ilike(f"%{token}%"),
            )
        )
        stmt = _apply_filters(stmt)
        result = await db.execute(stmt)
        products = result.scalars().all()
        if products:
            conf = 0.6 if (crop_filter or disease_filter) else 0.5
            return _pick_best(products, conf)

    # 5순위: 퍼지 매칭 (편집거리 기반 — STT 오인식 보정용)
    # 예: "오스피란" → "모스피란" 같이 한 글자만 다른 케이스
    from rapidfuzz import fuzz, process

    stmt = select(
        PesticideProduct.ingredient_or_formulation_name, PesticideProduct.brand_name
    )
    stmt = _apply_filters(stmt)
    result = await db.execute(stmt)
    rows = result.all()
    if rows:
        candidates: set[str] = set()
        for ingredient_name, brand_name in rows:
            if ingredient_name:
                candidates.add(ingredient_name)
            if brand_name:
                candidates.add(brand_name)

        best = process.extractOne(
            raw_name,
            list(candidates),
            scorer=fuzz.ratio,
            score_cutoff=75,
        )
        if best:
            matched_name = best[0]
            stmt2 = select(PesticideProduct).where(
                or_(
                    PesticideProduct.ingredient_or_formulation_name == matched_name,
                    PesticideProduct.brand_name == matched_name,
                )
            )
            stmt2 = _apply_filters(stmt2)
            r2 = await db.execute(stmt2)
            products = r2.scalars().all()
            if products:
                conf = 0.55 if (crop_filter or disease_filter) else 0.4
                return _pick_best(products, conf)

    return None


async def enrich_with_pesticide_match(db: AsyncSession, parse_result: dict) -> dict:
    """파싱 결과에 농약 매칭 정보를 추가하는 후처리 함수."""
    parsed = parse_result.get("parsed", {})
    pesticide_name = parsed.get("usage_pesticide_product")

    if not pesticide_name:
        return parse_result

    # 작물 + 병해충 정보를 매칭 힌트로 활용
    crop = parsed.get("crop")
    disease = parsed.get("disease")

    match = await match_pesticide(db, pesticide_name, crop=crop, disease=disease)

    if match:
        parsed["usage_pesticide_product"] = match["matched_name"]
        parse_result["parsed"] = parsed

        confidence = parse_result.get("confidence", {})
        confidence["usage_pesticide_product"] = match["confidence"]
        parse_result["confidence"] = confidence

        parse_result["pesticide_match"] = match
    else:
        confidence = parse_result.get("confidence", {})
        confidence["usage_pesticide_product_verified"] = False
        parse_result["confidence"] = confidence

    return parse_result
