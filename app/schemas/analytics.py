from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime


class QuestionAnalytics(BaseModel):
    question_id: int
    question_text: str
    question_type: str
    total_answers: int
    # For multiple_choice / dropdown
    choice_distribution: Optional[Dict[str, int]] = None
    # For rating
    avg_rating: Optional[float] = None
    rating_distribution: Optional[Dict[str, int]] = None
    # For text_input
    sample_responses: Optional[List[str]] = None


class TrendPoint(BaseModel):
    date: str
    count: int


class SurveyAnalytics(BaseModel):
    survey_id: int
    survey_title: str
    total_responses: int
    responses_today: int
    responses_this_week: int
    completion_trend: List[TrendPoint]
    question_analytics: List[QuestionAnalytics]


class DashboardStats(BaseModel):
    total_surveys: int
    published_surveys: int
    total_responses: int
    responses_today: int
    responses_this_week: int = 0
    recent_surveys: List[Dict[str, Any]]
    completion_trend: List[TrendPoint] = []
    recent_activity: List[Dict[str, Any]] = []
