from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Answer(Base):
    __tablename__ = "answers"

    id = Column(Integer, primary_key=True, index=True)
    response_id = Column(Integer, ForeignKey("responses.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    # Stores the answer value — text, selected option, rating number, etc.
    value = Column(Text, nullable=True)
    # For structured data like multi-select
    value_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    response = relationship("Response", back_populates="answers")
    question = relationship("Question", back_populates="answers")
