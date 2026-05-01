from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.core.deps import get_current_user
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserOut, VerifyOTPRequest
from app.services.email import send_otp_email
import random
from datetime import datetime, timedelta, timezone

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_200_OK)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user and existing_user.is_active:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Check slug uniqueness if it's a new registration or changing slug
    existing_tenant = db.query(Tenant).filter(Tenant.slug == payload.tenant_slug).first()
    if existing_tenant and not (existing_user and existing_user.tenant_id == existing_tenant.id):
        # Check if this tenant has active users
        active_user_in_tenant = db.query(User).filter(User.tenant_id == existing_tenant.id, User.is_active == True).first()
        if active_user_in_tenant:
            raise HTTPException(status_code=400, detail="Tenant slug already taken")

    # Generate OTP
    otp = "".join([str(random.randint(0, 9)) for _ in range(6)])
    otp_expiry = datetime.now(timezone.utc) + timedelta(minutes=10)

    if existing_user:
        # Update existing inactive user
        existing_user.full_name = payload.full_name
        existing_user.hashed_password = hash_password(payload.password)
        existing_user.otp = otp
        existing_user.otp_expires_at = otp_expiry
        
        # Update tenant if needed
        tenant = db.query(Tenant).filter(Tenant.id == existing_user.tenant_id).first()
        if tenant:
            tenant.name = payload.tenant_name
            tenant.slug = payload.tenant_slug
        
        user = existing_user
    else:
        # Check if we can reuse the existing tenant (slug already exists but no active users)
        if existing_tenant:
            tenant = existing_tenant
            tenant.name = payload.tenant_name
        else:
            # Create new tenant
            tenant = Tenant(name=payload.tenant_name, slug=payload.tenant_slug)
            db.add(tenant)
            db.flush()

        user = User(
            tenant_id=tenant.id,
            email=payload.email,
            full_name=payload.full_name,
            hashed_password=hash_password(payload.password),
            role="admin",
            is_active=False,
            otp=otp,
            otp_expires_at=otp_expiry,
        )
        db.add(user)

    db.commit()
    
    # Send OTP email
    try:
        send_otp_email(user.email, otp)
    except Exception as e:
        # If email fails, we might want to log it and let the user know
        # In a real app, you might want to rollback the user creation or provide a 'resend' option
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send verification email. Please contact support. Error: {str(e)}"
        )
    
    return {"message": "OTP sent to your email. Please verify to complete registration."}


@router.post("/verify-otp", response_model=TokenResponse)
def verify_otp(payload: VerifyOTPRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_active:
        raise HTTPException(status_code=400, detail="User already verified")

    if not user.otp or user.otp != payload.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    if user.otp_expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="OTP expired")

    # Activate user
    user.is_active = True
    user.otp = None
    user.otp_expires_at = None
    db.commit()
    db.refresh(user)
    
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    
    token = create_access_token(str(user.id), {"tenant_id": user.tenant_id, "role": user.role})
    return TokenResponse(
        access_token=token,
        user=UserOut(
            id=user.id,
            user_uuid=user.user_uuid or "",
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            tenant_id=user.tenant_id,
            tenant_name=tenant.name if tenant else None,
        ),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Please verify your email first")
    
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
            user_uuid=user.user_uuid or "",
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
    if not current_user.user_uuid:
        import uuid
        current_user.user_uuid = str(uuid.uuid4())
        db.commit()
        db.refresh(current_user)

    return UserOut(
        id=current_user.id,
        user_uuid=current_user.user_uuid,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        tenant_id=current_user.tenant_id,
        tenant_name=tenant.name if tenant else None,
    )
