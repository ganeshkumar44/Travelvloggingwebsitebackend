import re
from typing import Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

PASSWORD_PATTERN = re.compile(
    r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@$%&])[a-zA-Z0-9!@$%&]{8,}$'
)

PROFILE_USERNAME_PATTERN = re.compile(
    r'^(?:[A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9._-]{0,148}[A-Za-z0-9])$',
)


def _validate_profile_url_field(v: Optional[str], label: str) -> Optional[str]:
    if v is None:
        return None
    t = v.strip() if isinstance(v, str) else str(v)
    if not t:
        return None
    p = urlparse(t)
    if p.scheme not in ('http', 'https'):
        raise ValueError(
            f'{label} must be a valid http or https profile URL.',
        )
    if not p.netloc:
        raise ValueError(
            f'{label} must be a valid profile URL.',
        )
    return t


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
    username: Optional[str] = Field(default=None, max_length=150)
    facebook: Optional[str] = Field(default=None, max_length=500)
    twitter: Optional[str] = Field(default=None, max_length=500)
    linkedin: Optional[str] = Field(default=None, max_length=500)
    youtube: Optional[str] = Field(default=None, max_length=500)
    instagram: Optional[str] = Field(default=None, max_length=500)

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

    @field_validator(
        'phone',
        'about_author',
        'profession',
        'username',
        'facebook',
        'twitter',
        'linkedin',
        'youtube',
        'instagram',
        mode='before',
    )
    @classmethod
    def optional_empty_to_none(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and v.strip() == '':
            return None
        return v

    @field_validator('username', mode='after')
    @classmethod
    def username_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if not PROFILE_USERNAME_PATTERN.fullmatch(v):
            raise ValueError(
                'Username may only use letters, numbers, periods, underscores, and hyphens '
                '(1-150 characters; invalid or special characters are not allowed).',
            )
        return v

    @field_validator('facebook', mode='after')
    @classmethod
    def validate_facebook_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_profile_url_field(v, 'Facebook URL')

    @field_validator('twitter', mode='after')
    @classmethod
    def validate_twitter_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_profile_url_field(v, 'Twitter URL')

    @field_validator('linkedin', mode='after')
    @classmethod
    def validate_linkedin_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_profile_url_field(v, 'LinkedIn URL')

    @field_validator('youtube', mode='after')
    @classmethod
    def validate_youtube_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_profile_url_field(v, 'YouTube URL')

    @field_validator('instagram', mode='after')
    @classmethod
    def validate_instagram_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_profile_url_field(v, 'Instagram URL')


class DeleteProfileRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(..., min_length=1, description='Current password is required')


class DeleteProfileSuccess(BaseModel):
    message: str


RESET_PASSWORD_PATTERN = re.compile(
    r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%&])[a-zA-Z0-9!@#$%&]{8,}$'
)


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    current_password: str = Field(
        ...,
        min_length=1,
        description='Current password is required',
    )
    new_password: str = Field(
        ...,
        min_length=1,
        description='New password is required',
    )
    confirm_new_password: str = Field(
        ...,
        min_length=1,
        description='Confirm new password is required',
    )

    @field_validator('new_password')
    @classmethod
    def new_password_strength(cls, v: str) -> str:
        if not RESET_PASSWORD_PATTERN.fullmatch(v):
            raise ValueError(
                'Password must be at least 8 characters and include at least one '
                'lowercase letter, one uppercase letter, one number, and one special '
                'character from !@#$%& only',
            )
        return v

    @model_validator(mode='after')
    def new_passwords_match(self):
        if self.new_password != self.confirm_new_password:
            raise ValueError('New password and confirm new password do not match')
        return self


class ChangePasswordSuccess(BaseModel):
    message: str


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
