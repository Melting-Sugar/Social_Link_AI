from pydantic import BaseModel, EmailStr, field_validator, model_validator

from app.core.security import validate_password_strength


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    password_confirm: str

    @field_validator("username")
    @classmethod
    def username_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not (3 <= len(v) <= 64):
            raise ValueError("ユーザー名は3〜64文字で入力してください。")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        validate_password_strength(v)
        return v

    @model_validator(mode="after")
    def passwords_match(self) -> "RegisterRequest":
        if self.password != self.password_confirm:
            raise ValueError("パスワードが一致しません。")
        return self


class LoginRequest(BaseModel):
    # §11.2: email OR username, same field either way.
    identifier: str
    password: str


class ForgotUsernameRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
    new_password_confirm: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        validate_password_strength(v)
        return v

    @model_validator(mode="after")
    def passwords_match(self) -> "ResetPasswordRequest":
        if self.new_password != self.new_password_confirm:
            raise ValueError("パスワードが一致しません。")
        return self


class TokenResponse(BaseModel):
    # Only the access token goes in the response body — the refresh token
    # is set as an httpOnly cookie by the endpoint itself (§5).
    access_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    message: str
