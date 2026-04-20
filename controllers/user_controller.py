import secrets

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth.auth_handler import hash_password, verify_password, create_access_token
from models.user_model import User
from schemas.user_schema import UserCreate, UserLogin, RegistrationOtpVerify
from services.registration_email import RegistrationEmailError, send_registration_email


def _generate_unique_registration_code(db: Session) -> str:
    for _ in range(100):
        code = f'{secrets.randbelow(1_000_000):06d}'
        taken = (
            db.query(User.id)
            .filter(User.firsttime_register_code == code)
            .first()
        )
        if not taken:
            return code
    raise HTTPException(
        status_code=500,
        detail='Could not generate a unique verification code. Please try again.',
    )


def get_all_users(db: Session):
    return db.query(User).all()


def create_user(user: UserCreate, db: Session):
    existing_user = db.query(User).filter(User.email == user.email).first()

    if existing_user:
        return None

    hashed_password = hash_password(user.password)

    registration_code = _generate_unique_registration_code(db)

    new_user = User(
        firstname=user.firstname,
        lastname=user.lastname,
        email=user.email,
        phone=user.phone,
        password=hashed_password,
        gender=user.gender,
        firsttime_register_code=registration_code,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    try:
        send_registration_email(new_user.email, registration_code)
    except RegistrationEmailError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

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

    if not existing_user.is_verified:
        raise HTTPException(
            status_code=403,
            detail='Your email is not verified. Please verify your OTP before login.',
        )

    token = create_access_token(data={'sub': existing_user.email})

    return {
        'access_token': token,
        'token_type': 'bearer'
    }


def verify_registration_otp(payload: RegistrationOtpVerify, db: Session):
    entered_email_lower = payload.email.lower()
    otp = payload.otp.strip()

    user = (
        db.query(User)
        .filter(func.lower(User.email) == entered_email_lower)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=400,
            detail='Invalid email or verification code.',
        )

    if user.is_verified:
        raise HTTPException(
            status_code=400,
            detail='Email is already verified.',
        )

    if user.firsttime_register_code is None:
        raise HTTPException(
            status_code=400,
            detail='No verification code pending for this account.',
        )

    if user.firsttime_register_code != otp:
        raise HTTPException(
            status_code=400,
            detail='Invalid email or verification code.',
        )

    user.firsttime_register_code = None
    user.is_verified = True
    db.commit()

    return {'message': 'Email verification completed successfully.'}
