from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    user_id = payload.get("sub")
    from app.models.tenant import Tenant
    user = db.query(User).join(Tenant, User.tenant_id == Tenant.id)\
        .filter(User.id == int(user_id), User.is_active == True, Tenant.is_active == True).first()
    
    if not user:
        # Check if user exists but tenant is inactive
        existing = db.query(User).filter(User.id == int(user_id)).first()
        if existing:
            tenant = db.query(Tenant).filter(Tenant.id == existing.tenant_id).first()
            if tenant and not tenant.is_active:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization is suspended")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or disabled")
    return user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin access required")
    return current_user
