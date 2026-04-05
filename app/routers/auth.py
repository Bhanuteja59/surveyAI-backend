from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.core.deps import get_current_user
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    # Check slug uniqueness
    if db.query(Tenant).filter(Tenant.slug == payload.tenant_slug).first():
        raise HTTPException(status_code=400, detail="Tenant slug already taken")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    tenant = Tenant(name=payload.tenant_name, slug=payload.tenant_slug)
    db.add(tenant)
    db.flush()

    user = User(
        tenant_id=tenant.id,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role="admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.refresh(tenant)

    token = create_access_token(str(user.id), {"tenant_id": tenant.id, "role": user.role})
    return TokenResponse(
        access_token=token,
        user=UserOut(
            id=user.id,
            user_uuid=user.user_uuid,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            tenant_id=user.tenant_id,
            tenant_name=tenant.name,
        ),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    # Auto-promote bunny@gmail.com to super admin if not already
    if user.email == "bunny@gmail.com" and user.role != "super_admin":
        user.role = "super_admin"
        db.commit()
        db.refresh(user)

    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    if tenant and not tenant.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization is suspended")

    token = create_access_token(str(user.id), {"tenant_id": user.tenant_id, "role": user.role})
    return TokenResponse(
        access_token=token,
        user=UserOut(
            id=user.id,
            user_uuid=user.user_uuid,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            tenant_id=user.tenant_id,
            tenant_name=tenant.name if tenant else None,
        ),
    )


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    return UserOut(
        id=current_user.id,
        user_uuid=current_user.user_uuid,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        tenant_id=current_user.tenant_id,
        tenant_name=tenant.name if tenant else None,
    )
