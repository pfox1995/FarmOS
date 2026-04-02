from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
def get_me(
    x_user_id: int = Header(default=1, alias="X-User-Id"),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == x_user_id).first()
    if not user:
        user = db.query(User).filter(User.id == 1).first()
    return user
