from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.crud.review import get_product_reviews
from app.schemas.review import ReviewResponse

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.get("/product/{product_id}", response_model=List[ReviewResponse])
def list_product_reviews(product_id: int, db: Session = Depends(get_db)):
    return get_product_reviews(db, product_id)
