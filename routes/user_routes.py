from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from database import get_db
from controllers.user_controller import get_all_users, create_user, login_user
from schemas.user_schema import UserCreate, UserResponse, UserLogin, TokenResponse
from auth.auth_handler import verify_token

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

@router.post('/login', response_model=TokenResponse)
def login(
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
def get_profile(current_user: str = Depends(verify_token)):
    return {
        'message': 'Profile fetched successfully',
        'email': current_user
    }