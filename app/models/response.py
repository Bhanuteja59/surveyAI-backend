from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Response(Base):
    __tablename__ = "responses"

    id = Column(Integer, primary_key=True, index=True)
    survey_id = Column(Integer, ForeignKey("surveys.id"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    respondent_email = Column(String(255), nullable=True)
    respondent_name = Column(String(255), nullable=True)
    ip_address = Column(String(50), nullable=True)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    survey = relationship("Survey", back_populates="responses")
    answers = relationship("Answer", back_populates="response", cascade="all, delete-orphan")
