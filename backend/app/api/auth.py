import secrets
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from app.core import user_store
from app.models.user import User
from app.schemas.auth import (
    SignupRequest, LoginRequest, FindIdRequest, FindPasswordRequest,
    ResetPasswordRequest, UserResponse, OnboardingRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_KEY = "farmos_token"

# 비밀번호 재설정용 일회용 토큰 저장소 (인메모리, 5분 만료)
_reset_tokens: dict[str, dict] = {}  # {token: {"user_id": str, "expires": float}}
RESET_TOKEN_EXPIRE_SECONDS = 300  # 5분

# 로그인 브루트포스 방어 — IP별 시도 횟수 제한
_login_attempts: dict[str, list[float]] = defaultdict(list)
MAX_LOGIN_ATTEMPTS = 5    # 최대 시도 횟수
LOGIN_WINDOW_SECONDS = 60  # 시간 윈도우 (1분)


def _check_rate_limit(client_ip: str):
    """IP별 로그인 시도 횟수를 확인하고 초과 시 차단."""
    now = time.time()
    # 윈도우 밖의 오래된 기록 제거
    _login_attempts[client_ip] = [
        t for t in _login_attempts[client_ip]
        if now - t < LOGIN_WINDOW_SECONDS
    ]
    if len(_login_attempts[client_ip]) >= MAX_LOGIN_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="로그인 시도가 너무 많습니다. 1분 후 다시 시도해주세요.",
        )
    _login_attempts[client_ip].append(now)


def _set_token_cookie(response: Response, token: str):
    response.set_cookie(
        key=COOKIE_KEY,
        value=token,
        httponly=True,
        secure=False,       # 개발환경 HTTP → False, 프로덕션에서는 True
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


def _user_response(user: User) -> UserResponse:
    """User 모델 → UserResponse 변환 헬퍼."""
    return UserResponse(
        user_id=user.id, name=user.name, email=user.email,
        location=user.location, area=user.area, farmname=user.farmname,
        profile=user.profile, status=user.status,
        onboarding_completed=user.onboarding_completed,
        main_crop=user.main_crop, crop_variety=user.crop_variety,
        farmland_type=user.farmland_type,
        is_promotion_area=user.is_promotion_area,
        has_farm_registration=user.has_farm_registration,
        farmer_type=user.farmer_type,
        years_rural_residence=user.years_rural_residence,
        years_farming=user.years_farming,
    )


@router.post("/signup", response_model=UserResponse, status_code=201)
async def signup(req: SignupRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """회원가입 — 계정 생성 후 자동 로그인(쿠키 설정)."""
    user = await user_store.create_user(
        db, user_id=req.user_id, name=req.name, email=req.email,
        password=req.password, location=req.location,
        area=req.area, farmname=req.farmname, profile=req.profile,
    )
    if not user:
        raise HTTPException(400, "이미 사용 중인 아이디 또는 이메일입니다.")
    token = create_access_token({"sub": user.id, "name": user.name})
    _set_token_cookie(response, token)
    return _user_response(user)


@router.post("/login")
async def login(req: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """로그인 — HttpOnly 쿠키로 JWT 설정 (IP별 시도 횟수 제한)."""
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    user = await user_store.authenticate(db, req.user_id, req.password)
    if not user:
        raise HTTPException(401, "아이디 또는 비밀번호가 올바르지 않습니다.")

    # 로그인 성공 시 해당 IP의 시도 기록 초기화
    _login_attempts.pop(client_ip, None)
    token = create_access_token({"sub": user.id, "name": user.name})
    _set_token_cookie(response, token)
    return {"user_id": user.id, "name": user.name}


@router.post("/logout")
async def logout(response: Response):
    """로그아웃 — 쿠키 삭제."""
    response.delete_cookie(key=COOKIE_KEY, path="/")
    return {"message": "로그아웃되었습니다."}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """현재 로그인한 사용자 정보 반환 — 쿠키 토큰 검증."""
    return _user_response(current_user)


@router.put("/onboarding", response_model=UserResponse)
async def complete_onboarding(
    req: OnboardingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """온보딩 완료 — 농장 프로필 저장."""
    user = await user_store.update_onboarding(db, current_user, req.model_dump(exclude_unset=True))
    return _user_response(user)


@router.post("/find-id")
async def find_id(req: FindIdRequest, db: AsyncSession = Depends(get_db)):
    """아이디 찾기 — 이름 + 이메일로 조회."""
    user = await user_store.find_by_name_and_email(db, req.name, req.email)
    if not user:
        raise HTTPException(404, "일치하는 회원 정보를 찾을 수 없습니다.")
    uid = user.id
    masked = uid[:2] + "*" * (len(uid) - 2)
    return {"user_id_masked": masked, "message": "아이디를 찾았습니다."}


@router.post("/find-password")
async def find_password(req: FindPasswordRequest, db: AsyncSession = Depends(get_db)):
    """비밀번호 찾기 — 아이디 + 이메일 확인 후 일회용 재설정 토큰 발급."""
    user = await user_store.find_by_id_and_email(db, req.user_id, req.email)
    if not user:
        raise HTTPException(404, "일치하는 회원 정보를 찾을 수 없습니다.")

    # 만료된 토큰 정리
    now = time.time()
    expired = [k for k, v in _reset_tokens.items() if v["expires"] < now]
    for k in expired:
        del _reset_tokens[k]

    # 일회용 재설정 토큰 발급
    reset_token = secrets.token_urlsafe(32)
    _reset_tokens[reset_token] = {
        "user_id": req.user_id,
        "expires": now + RESET_TOKEN_EXPIRE_SECONDS,
    }
    return {
        "verified": True,
        "reset_token": reset_token,
        "message": "본인 확인이 완료되었습니다. 새 비밀번호를 설정하세요.",
    }


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """비밀번호 재설정 — 일회용 토큰 검증 후 변경."""
    token_data = _reset_tokens.get(req.reset_token)
    if not token_data or token_data["expires"] < time.time():
        _reset_tokens.pop(req.reset_token, None)
        raise HTTPException(400, "재설정 토큰이 유효하지 않거나 만료되었습니다.")

    if token_data["user_id"] != req.user_id:
        raise HTTPException(400, "잘못된 요청입니다.")

    ok = await user_store.reset_password(db, req.user_id, req.new_password)
    if not ok:
        raise HTTPException(404, "사용자를 찾을 수 없습니다.")

    # 토큰 소멸 (일회용)
    del _reset_tokens[req.reset_token]
    return {"message": "비밀번호가 성공적으로 변경되었습니다."}
