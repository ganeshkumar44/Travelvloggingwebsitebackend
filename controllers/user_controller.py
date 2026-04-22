import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth.auth_handler import hash_password, verify_password, create_access_token
from models.user_model import User
from schemas.user_schema import (
    DeleteProfileRequest,
    ForgotPasswordOtpVerify,
    ProfileUpdateRequest,
    ResetPasswordRequest,
    UserCreate,
    UserLogin,
    RegistrationOtpVerify,
)
from services.forgot_password_email import ForgotPasswordEmailError, send_forgot_password_otp_email
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


def _generate_unique_forget_password_code(db: Session) -> str:
    for _ in range(100):
        code = f'{secrets.randbelow(1_000_000):06d}'
        taken = (
            db.query(User.id)
            .filter(User.forget_password_code == code)
            .first()
        )
        if not taken:
            return code
    raise HTTPException(
        status_code=500,
        detail='Could not generate a unique verification code. Please try again.',
    )


def request_forgot_password(email: str, db: Session):
    entered_email_lower = email.lower()
    user = (
        db.query(User)
        .filter(func.lower(User.email) == entered_email_lower)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=400,
            detail='No account is registered with this email address.',
        )

    otp = _generate_unique_forget_password_code(db)
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    user.forget_password_code = otp
    user.forget_password_code_expires = expires_at
    db.commit()
    db.refresh(user)

    try:
        send_forgot_password_otp_email(user.email, otp)
    except ForgotPasswordEmailError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        'message': 'A verification code has been sent to your email address.',
    }


def verify_forgot_password_otp(payload: ForgotPasswordOtpVerify, db: Session):
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

    if user.forget_password_code is None and user.forget_password_code_expires is None:
        raise HTTPException(
            status_code=400,
            detail='No password reset verification is pending for this account.',
        )

    if user.forget_password_code is None and user.forget_password_code_expires is not None:
        if user.forget_password_code_expires > datetime.utcnow():
            raise HTTPException(
                status_code=400,
                detail='This email has already been verified. Please proceed to reset your password.',
            )
        raise HTTPException(
            status_code=400,
            detail='No password reset verification is pending for this account.',
        )

    if user.forget_password_code_expires is None:
        raise HTTPException(
            status_code=400,
            detail='No password reset verification is pending for this account.',
        )

    if user.forget_password_code_expires <= datetime.utcnow():
        raise HTTPException(
            status_code=400,
            detail='This verification code has expired. Please request a new code.',
        )

    if user.forget_password_code != otp:
        raise HTTPException(
            status_code=400,
            detail='Invalid email or verification code.',
        )

    user.forget_password_code = None
    user.forget_password_code_expires = datetime.utcnow() + timedelta(minutes=10)
    db.commit()

    return {
        'message': 'Verification successful. You may now reset your password.',
    }


def reset_password_after_forgot(payload: ResetPasswordRequest, db: Session):
    entered_email_lower = payload.email.lower()

    user = (
        db.query(User)
        .filter(func.lower(User.email) == entered_email_lower)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=400,
            detail='No account is registered with this email address.',
        )

    if (
        user.forget_password_code is not None
        or user.forget_password_code_expires is None
        or user.forget_password_code_expires <= datetime.utcnow()
    ):
        raise HTTPException(
            status_code=400,
            detail='Password reset is not allowed. Please verify your OTP again or request a new code.',
        )

    user.password = hash_password(payload.new_password)
    user.forget_password_code = None
    user.forget_password_code_expires = None
    db.commit()

    return {'message': 'Your password has been reset successfully.'}


def update_user_profile(current_email: str, payload: ProfileUpdateRequest, db: Session):
    user = db.query(User).filter(User.email == current_email).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail='User not found',
        )

    updates = payload.model_dump(exclude_unset=True)

    for key in (
        'firstname',
        'lastname',
        'phone',
        'gender',
        'about_author',
        'profession',
        'username',
        'facebook',
        'twitter',
        'linkedin',
        'youtube',
        'instagram',
    ):
        if key in updates:
            setattr(user, key, updates[key])

    db.commit()
    db.refresh(user)

    return {
        'message': 'Profile updated successfully',
        'firstname': user.firstname,
        'lastname': user.lastname,
        'username': user.username,
        'email': user.email,
        'phone': user.phone,
        'gender': user.gender,
        'role': user.role,
        'about_author': user.about_author,
        'profession': user.profession,
        'facebook': user.facebook,
        'twitter': user.twitter,
        'linkedin': user.linkedin,
        'youtube': user.youtube,
        'instagram': user.instagram,
    }


def delete_user_account(current_email: str, payload: DeleteProfileRequest, db: Session):
    user = db.query(User).filter(User.email == current_email).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail='User not found',
        )

    if payload.email.lower() != user.email.lower():
        raise HTTPException(
            status_code=403,
            detail='The email address does not match the signed-in account.',
        )

    if not verify_password(payload.password, user.password):
        raise HTTPException(
            status_code=401,
            detail='The password is incorrect.',
        )

    db.delete(user)
    db.commit()

    return {'message': 'Your account has been deleted successfully.'}
