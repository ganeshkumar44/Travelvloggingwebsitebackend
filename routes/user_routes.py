from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from controllers.user_controller import get_all_users, create_user
from schemas.user_schema import UserCreate, UserResponse

router = APIRouter(prefix='/users', tags=['Users'])

@router.get('/', response_model=list[UserResponse])
def get_users(db: Session = Depends(get_db)):
    return get_all_users(db)

@router.post('/', response_model=UserResponse)
def add_user(user: UserCreate, db: Session = Depends(get_db)):
    created_user = create_user(user, db)

    if not created_user:
        raise HTTPException(status_code=400, detail='Email already exists')

    return created_user