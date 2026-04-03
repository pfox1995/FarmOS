from sqlalchemy.orm import Session, joinedload
from app.models.review import Review


def get_product_reviews(db: Session, product_id: int):
    return (
        db.query(Review)
        .options(joinedload(Review.user))
        .filter(Review.product_id == product_id)
        .order_by(Review.created_at.desc())
        .all()
    )
