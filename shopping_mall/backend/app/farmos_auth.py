"""FarmOS JWT 세션 공유 — farmos_token 쿠키에서 사용자 정보 추출."""

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt

from app.core.config import settings

# FarmOS 백엔드와 동일한 JWT 시크릿 키를 사용해야 함
# 환경변수 JWT_SECRET_KEY를 양쪽에서 공유
FARMOS_SECRET_KEY = settings.jwt_secret_key
ALGORITHM = "HS256"
COOKIE_KEY = "farmos_token"


class FarmOSUser:
    """FarmOS JWT에서 추출한 사용자 정보."""

    def __init__(self, user_id: str, name: str):
        self.user_id = user_id
        self.name = name


def get_farmos_user_optional(request: Request) -> FarmOSUser | None:
    """쿠키에서 FarmOS JWT를 읽어 사용자 정보 추출. 미인증이면 None 반환."""
    token = request.cookies.get(COOKIE_KEY)
    if not token or not FARMOS_SECRET_KEY:
        return None
    try:
        payload = jwt.decode(token, FARMOS_SECRET_KEY, algorithms=[ALGORITHM])
        # Refresh Token 거부 — Access Token만 허용
        if payload.get("type") != "access":
            return None
        user_id = payload.get("sub", "")
        name = payload.get("name", "")
        if not user_id:
            return None
        return FarmOSUser(user_id=user_id, name=name)
    except JWTError:
        return None


def get_farmos_user_required(request: Request) -> FarmOSUser:
    """쿠키에서 FarmOS JWT를 읽어 사용자 정보 추출. 미인증이면 401."""
    user = get_farmos_user_optional(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="FarmOS 로그인이 필요합니다.",
        )
    return user
