from pydantic import BaseModel, EmailStr
from typing import Optional

class UserCreate(BaseModel):
    firstname: str
    lastname: str
    email: EmailStr
    phone: Optional[str] = None
    password: str
    gender: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: int
    firstname: str
    lastname: str
    email: EmailStr
    phone: Optional[str]
    gender: Optional[str]
    role: str
    is_verified: bool

    class Config:
        from_attributes = True
