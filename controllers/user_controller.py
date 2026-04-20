from sqlalchemy import func
from sqlalchemy.orm import Session
from models.user_model import User
from schemas.user_schema import UserCreate, UserLogin
from auth.auth_handler import hash_password, verify_password, create_access_token


def get_all_users(db: Session):
    return db.query(User).all()


def create_user(user: UserCreate, db: Session):
    existing_user = db.query(User).filter(User.email == user.email).first()

    if existing_user:
        return None

    hashed_password = hash_password(user.password)

    new_user = User(
        firstname=user.firstname,
        lastname=user.lastname,
        email=user.email,
        phone=user.phone,
        password=hashed_password,
        gender=user.gender
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


def login_user(user: UserLogin, db: Session):
    entered_email_lower = user.email.lower()
    existing_user = (
        db.query(User)
        .filter(func.lower(User.email) == entered_email_lower)
        .first()
    )

    if not existing_user:
        return None

    if not verify_password(user.password, existing_user.password):
        return None

    token = create_access_token(data={'sub': existing_user.email})

    return {
        'access_token': token,
        'token_type': 'bearer'
    }
