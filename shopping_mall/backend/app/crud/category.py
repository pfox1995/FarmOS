from sqlalchemy.orm import Session, joinedload
from app.models.category import Category


def get_categories_tree(db: Session):
    return (
        db.query(Category)
        .filter(Category.parent_id.is_(None))
        .options(joinedload(Category.children))
        .order_by(Category.sort_order)
        .all()
    )
