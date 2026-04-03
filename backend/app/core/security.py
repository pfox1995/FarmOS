"""JWT 토큰 생성/검증 및 비밀번호 Bcrypt 해싱."""

from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

import secrets

from app.core.config import settings

# settings.JWT_SECRET_KEY가 있으면 고정 키 사용,
# 없으면 서버 시작마다 랜덤 생성 → 재시작 시 기존 세션 자동 무효화 (개발)
SECRET_KEY = settings.JWT_SECRET_KEY or secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# 서버 시작마다 새로 생성 — 재시작 시 기존 토큰 무효화
SERVER_BOOT_ID = secrets.token_urlsafe(8)
print(f"[Security] SERVER_BOOT_ID = {SERVER_BOOT_ID}")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "bid": SERVER_BOOT_ID})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        token_bid = payload.get("bid")
        print(f"[Security] token bid={token_bid}, server bid={SERVER_BOOT_ID}, match={token_bid == SERVER_BOOT_ID}")
        # boot_id가 현재 서버와 다르면 재시작된 것 → 토큰 무효
        if token_bid != SERVER_BOOT_ID:
            return None
        return payload
    except JWTError:
        return None
