from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    survey_id = Column(Integer, ForeignKey("surveys.id"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    question_type = Column(String(50), nullable=False)
    # Types: multiple_choice, rating, text_input, dropdown
    options = Column(JSON, nullable=True)
    # For multiple_choice/dropdown: {"choices": ["Option A", "Option B"]}
    # For rating: {"min": 1, "max": 5, "labels": {"1": "Poor", "5": "Excellent"}}
    is_required = Column(Boolean, default=True)
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    survey = relationship("Survey", back_populates="questions")
    answers = relationship("Answer", back_populates="question", cascade="all, delete-orphan")
