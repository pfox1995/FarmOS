from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.crud.category import get_categories_tree
from app.schemas.category import CategoryTree

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("/", response_model=List[CategoryTree])
def list_categories(db: Session = Depends(get_db)):
    return get_categories_tree(db)
