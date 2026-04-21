from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from database import get_db
from controllers.user_controller import (
    get_all_users,
    create_user,
    login_user,
    verify_registration_otp,
    request_forgot_password,
    verify_forgot_password_otp,
    reset_password_after_forgot,
    update_user_profile,
)
from schemas.user_schema import (
    UserCreate,
    UserResponse,
    UserLogin,
    TokenResponse,
    RegistrationOtpVerify,
    EmailVerificationSuccess,
    ForgotPasswordRequest,
    ForgotPasswordSuccess,
    ForgotPasswordOtpVerify,
    VerifyForgotPasswordOtpSuccess,
    ResetPasswordRequest,
    ResetPasswordSuccess,
    ProfileUpdateRequest,
)
from auth.auth_handler import verify_token
from models.user_model import User

router = APIRouter(tags=['Users'])

@router.get('/users', response_model=list[UserResponse])
def get_users(db: Session = Depends(get_db)):
    return get_all_users(db)

@router.post('/register', response_model=UserResponse)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    created_user = create_user(user, db)

    if not created_user:
        raise HTTPException(
            status_code=400,
            detail='Email already exists'
        )

    return created_user


@router.post('/verify-registration-otp', response_model=EmailVerificationSuccess)
def verify_registration_otp_route(
    payload: RegistrationOtpVerify,
    db: Session = Depends(get_db),
):
    return verify_registration_otp(payload, db)


@router.post('/forgot-password', response_model=ForgotPasswordSuccess)
def forgot_password_route(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    return request_forgot_password(payload.email, db)


@router.post('/verify-forgot-password-otp', response_model=VerifyForgotPasswordOtpSuccess)
def verify_forgot_password_otp_route(
    payload: ForgotPasswordOtpVerify,
    db: Session = Depends(get_db),
):
    return verify_forgot_password_otp(payload, db)


@router.post('/reset-password', response_model=ResetPasswordSuccess)
def reset_password_route(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    return reset_password_after_forgot(payload, db)


@router.post('/login', response_model=TokenResponse)
def login(user: UserLogin, db: Session = Depends(get_db)):
    logged_in_user = login_user(user, db)

    if not logged_in_user:
        raise HTTPException(
            status_code=401,
            detail='Invalid email or password'
        )

    return logged_in_user


@router.post('/loginform', response_model=TokenResponse)
def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user_data = UserLogin(
        email=form_data.username,
        password=form_data.password
    )

    logged_in_user = login_user(user_data, db)

    if not logged_in_user:
        raise HTTPException(
            status_code=401,
            detail='Invalid email or password'
        )

    return logged_in_user

@router.get('/profile')
def get_profile(
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == current_user).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail='User not found'
        )

    return {
        'message': 'Profile fetched successfully',
        'firstname': user.firstname,
        'lastname': user.lastname,
        'email': user.email,
        'phone': user.phone,
        'gender': user.gender,
        'role': user.role,
        'about_author': user.about_author,
        'profession': user.profession,
    }


@router.patch('/profile')
def update_profile(
    payload: ProfileUpdateRequest,
    current_user: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    return update_user_profile(current_user, payload, db)