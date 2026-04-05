from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class AIInsight(Base):
    __tablename__ = "ai_insights"

    id = Column(Integer, primary_key=True, index=True)
    survey_id = Column(Integer, ForeignKey("surveys.id"), nullable=False, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    overall_sentiment = Column(String(50), nullable=True)   # positive, negative, neutral, mixed
    sentiment_score = Column(String(10), nullable=True)     # e.g. "0.72"
    summary = Column(Text, nullable=True)
    key_insights = Column(JSON, nullable=True)              # list of insight strings
    suggestions = Column(JSON, nullable=True)               # list of suggestion strings
    question_insights = Column(JSON, nullable=True)         # per-question analysis
    total_responses_analyzed = Column(Integer, default=0)
    status = Column(String(20), default="pending")          # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    survey = relationship("Survey", back_populates="ai_insights")
