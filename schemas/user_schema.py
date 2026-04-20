import re
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

PASSWORD_PATTERN = re.compile(
    r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@$%&])[a-zA-Z0-9!@$%&]{8,}$'
)


class UserCreate(BaseModel):
    firstname: str = Field(..., min_length=1, description='First name is required')
    lastname: str = Field(..., min_length=1, description='Last name is required')
    email: EmailStr = Field(
        ...,
        description='Valid email address is required',
    )
    phone: str = Field(..., min_length=1, description='Phone number is required')
    password: str = Field(..., min_length=1, description='Password is required')
    confirm_password: str = Field(
        ...,
        min_length=1,
        description='Confirm password is required',
    )
    gender: Literal['Male', 'Female', 'Other']

    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not PASSWORD_PATTERN.fullmatch(v):
            raise ValueError(
                'Password must be at least 8 characters and include at least one '
                'lowercase letter, one uppercase letter, one number, and one special '
                'character from !@$%& only'
            )
        return v

    @model_validator(mode='after')
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError('Password and Confirm Password do not match')
        return self

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
