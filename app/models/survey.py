from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import secrets
from app.core.database import Base


class Survey(Base):
    __tablename__ = "surveys"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    public_token = Column(String(64), unique=True, index=True, default=lambda: secrets.token_urlsafe(32))
    is_active = Column(Boolean, default=True)
    is_published = Column(Boolean, default=False)
    webhook_url = Column(String(1000), nullable=True)
    webhook_secret = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    tenant = relationship("Tenant", back_populates="surveys")
    creator = relationship("User")
    questions = relationship("Question", back_populates="survey", cascade="all, delete-orphan", order_by="Question.order_index")
    responses = relationship("Response", back_populates="survey", cascade="all, delete-orphan")
    ai_insights = relationship("AIInsight", back_populates="survey", cascade="all, delete-orphan")
