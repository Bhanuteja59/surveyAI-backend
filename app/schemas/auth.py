from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional


class TenantCreate(BaseModel):
    name: str
    slug: str

    @field_validator("slug")
    @classmethod
    def slug_alphanumeric(cls, v: str) -> str:
        import re
        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError("Slug must be lowercase alphanumeric with hyphens only")
        return v


class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    tenant_name: str
    tenant_slug: str

    @field_validator("password")
    @classmethod
    def password_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    id: int
    user_uuid: str
    email: str
    full_name: str
    role: str
    tenant_id: int
    tenant_name: Optional[str] = None

    class Config:
        from_attributes = True


TokenResponse.model_rebuild()
