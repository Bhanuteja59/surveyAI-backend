from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid
from app.core.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    member = "member"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_uuid = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="admin", nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tenant = relationship("Tenant", back_populates="users")
