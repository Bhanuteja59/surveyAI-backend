from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime


class AIInsightOut(BaseModel):
    id: int
    survey_id: int
    overall_sentiment: Optional[str]
    sentiment_score: Optional[str]
    summary: Optional[str]
    key_insights: Optional[List[str]]
    suggestions: Optional[List[str]]
    question_insights: Optional[List[Dict[str, Any]]]
    total_responses_analyzed: int
    status: str
    generated_at: datetime

    class Config:
        from_attributes = True


class AIInsightTrigger(BaseModel):
    survey_id: int
