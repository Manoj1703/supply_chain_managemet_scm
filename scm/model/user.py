import re

from pydantic import BaseModel, Field, field_validator, model_validator


EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
)


def _validate_email_format(value: str) -> str:
    value = value.strip().lower()
    if not EMAIL_PATTERN.match(value):
        raise ValueError("Email must be a valid email address")
    return value


def _validate_password_strength(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not re.search(r"[A-Z]", value):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", value):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", value):
        raise ValueError("Password must contain at least one number")
    if not re.search(r"[^\w\s]", value):
        raise ValueError("Password must contain at least one special character")
    return value


class UserSignup(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validate_email_format(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _validate_password_strength(value)

    @field_validator("confirm_password")
    @classmethod
    def validate_confirm_password(cls, value: str) -> str:
        return _validate_password_strength(value)

    @model_validator(mode="after")
    def passwords_match(self) -> "UserSignup":
        if self.password != self.confirm_password:
            raise ValueError("Password and confirm password must match")
        return self


class UserLogin(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validate_email_format(value)


class UserPublic(BaseModel):
    id: str
    name: str
    email: str


class AuthResponse(BaseModel):
    message: str | None = None
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class UserData(BaseModel):
    name: str
    email: str


class PasswordVerifyRequest(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class PasswordVerifyResponse(BaseModel):
    message: str
    is_valid: bool


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return _validate_password_strength(value)

    @field_validator("confirm_new_password")
    @classmethod
    def validate_confirm_new_password(cls, value: str) -> str:
        return _validate_password_strength(value)

    @model_validator(mode="after")
    def new_passwords_match(self) -> "PasswordChangeRequest":
        if self.new_password != self.confirm_new_password:
            raise ValueError("Passwords do not match")
        return self
