from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any
from datetime import datetime


class AnswerCreate(BaseModel):
    question_id: int
    value: Optional[str] = None
    value_json: Optional[Any] = None


class ResponseSubmit(BaseModel):
    respondent_name: Optional[str] = None
    respondent_email: Optional[str] = None
    answers: List[AnswerCreate]


class AnswerOut(BaseModel):
    id: int
    question_id: int
    value: Optional[str]
    value_json: Optional[Any]

    class Config:
        from_attributes = True


class ResponseOut(BaseModel):
    id: int
    survey_id: int
    respondent_name: Optional[str]
    respondent_email: Optional[str]
    submitted_at: datetime
    answers: List[AnswerOut] = []

    class Config:
        from_attributes = True
