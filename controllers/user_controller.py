from sqlalchemy.orm import Session
from models.user_model import User
from schemas.user_schema import UserCreate


def get_all_users(db: Session):
    return db.query(User).all()


def create_user(user: UserCreate, db: Session):
    existing_user = db.query(User).filter(User.email == user.email).first()

    if existing_user:
        return None

    new_user = User(
        firstname=user.firstname,
        lastname=user.lastname,
        email=user.email,
        phone=user.phone,
        password=user.password,
        gender=user.gender
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user