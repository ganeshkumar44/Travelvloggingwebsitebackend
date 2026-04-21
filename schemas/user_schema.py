import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

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

class RegistrationOtpVerify(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=1, description='6-digit verification code')

    @field_validator('otp')
    @classmethod
    def otp_six_digits(cls, v: str) -> str:
        t = v.strip()
        if len(t) != 6 or not t.isdigit():
            raise ValueError('OTP must be a 6-digit numeric code')
        return t


class EmailVerificationSuccess(BaseModel):
    message: str


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


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    firstname: str = Field(..., min_length=1, max_length=100, description='First name is required')
    lastname: str = Field(..., min_length=1, max_length=100, description='Last name is required')
    phone: Optional[str] = Field(default=None, max_length=20)
    gender: Optional[Literal['Male', 'Female', 'Other']] = None
    about_author: Optional[str] = None
    profession: Optional[str] = Field(default=None, max_length=150)

    @field_validator('firstname')
    @classmethod
    def firstname_required(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('First name is required')
        return v.strip()

    @field_validator('lastname')
    @classmethod
    def lastname_required(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Last name is required')
        return v.strip()

    @field_validator('phone', 'about_author', 'profession', mode='before')
    @classmethod
    def optional_empty_to_none(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and v.strip() == '':
            return None
        return v


RESET_PASSWORD_PATTERN = re.compile(
    r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%&])[a-zA-Z0-9!@#$%&]{8,}$'
)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordSuccess(BaseModel):
    message: str


class ForgotPasswordOtpVerify(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=1, description='6-digit verification code')

    @field_validator('otp')
    @classmethod
    def otp_six_digits(cls, v: str) -> str:
        t = v.strip()
        if len(t) != 6 or not t.isdigit():
            raise ValueError('OTP must be a 6-digit numeric code')
        return t


class VerifyForgotPasswordOtpSuccess(BaseModel):
    message: str


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    new_password: str = Field(..., min_length=1, description='New password is required')
    confirm_password: str = Field(
        ...,
        min_length=1,
        description='Confirm password is required',
    )

    @field_validator('new_password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not RESET_PASSWORD_PATTERN.fullmatch(v):
            raise ValueError(
                'Password must be at least 8 characters and include at least one '
                'lowercase letter, one uppercase letter, one number, and one special '
                'character from !@#$%& only'
            )
        return v

    @model_validator(mode='after')
    def passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError('Password and Confirm Password do not match')
        return self


class ResetPasswordSuccess(BaseModel):
    message: str
