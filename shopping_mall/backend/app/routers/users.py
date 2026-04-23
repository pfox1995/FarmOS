import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse
from app.core.config import settings
from app.farmos_auth import get_farmos_user_optional, FarmOSUser

router = APIRouter(prefix="/api/users", tags=["users"])


def _resolve_user(request: Request, db: Session) -> tuple[User | None, FarmOSUser | None]:
    """FarmOS 쿠키 인증 우선, 없으면 X-User-Id 헤더 폴백."""
    farmos_user = get_farmos_user_optional(request)
    if farmos_user:
        user = db.query(User).filter(User.user_id == farmos_user.user_id).first()
        if not user:
            user = User(
                user_id=farmos_user.user_id,
                name=farmos_user.name,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user, farmos_user
    # 폴백: X-User-Id 헤더
    header_id = request.headers.get("X-User-Id", "1")
    try:
        uid = int(header_id)
    except ValueError:
        uid = 1
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        user = db.query(User).filter(User.id == 1).first()
    return user, None


@router.get("/me", response_model=UserResponse)
def get_me(request: Request, db: Session = Depends(get_db)):
    user, _ = _resolve_user(request, db)
    return user


@router.get("/auth/status")
def auth_status(request: Request, db: Session = Depends(get_db)):
    """FarmOS 세션 공유 상태 확인 — FarmOS 백엔드에 서버사이드 검증."""
    token = request.cookies.get("farmos_token")
    if not token:
        return {"authenticated": False}

    # FarmOS 백엔드에 직접 검증 요청
    try:
        res = httpx.get(
            f"{settings.farmos_api_url}/auth/me",
            cookies={"farmos_token": token},
            timeout=3.0,
        )
        if res.status_code != 200:
            return {"authenticated": False}
        farmos_data = res.json()
    except Exception:
        return {"authenticated": False}

    # FarmOS 인증 통과 → 쇼핑몰 DB에서 사용자 매칭
    name = farmos_data.get("name", "")
    user_id = farmos_data.get("user_id", "")

    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        user = User(user_id=user_id, name=name)
        db.add(user)
        db.commit()
        db.refresh(user)

    return {
        "authenticated": True,
        "login_id": user_id,
        "name": name,
        "shop_user_id": user.id,
    }
