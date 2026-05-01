from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class QuestionOption(BaseModel):
    choices: Optional[List[str]] = None
    min: Optional[int] = None
    max: Optional[int] = None
    labels: Optional[dict] = None


class QuestionCreate(BaseModel):
    text: str
    question_type: str  # multiple_choice | rating | text_input | dropdown
    options: Optional[dict] = None
    is_required: bool = True
    order_index: int = 0


class QuestionUpdate(BaseModel):
    text: Optional[str] = None
    question_type: Optional[str] = None
    options: Optional[dict] = None
    is_required: Optional[bool] = None
    order_index: Optional[int] = None


class QuestionOut(BaseModel):
    id: int
    survey_id: int
    text: str
    question_type: str
    options: Optional[dict] = None
    is_required: bool
    order_index: int

    class Config:
        from_attributes = True


class SurveyCreate(BaseModel):
    title: str
    description: Optional[str] = None
    questions: Optional[List[QuestionCreate]] = []


class SurveyUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    is_published: Optional[bool] = None
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None


class SurveyOut(BaseModel):
    id: int
    tenant_id: int
    title: str
    description: Optional[str]
    public_token: str
    is_active: bool
    is_published: bool
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime]
    questions: List[QuestionOut] = []
    response_count: Optional[int] = 0

    class Config:
        from_attributes = True


class SurveyListItem(BaseModel):
    id: int
    title: str
    description: Optional[str]
    public_token: str
    is_published: bool
    created_at: datetime
    response_count: int = 0

    class Config:
        from_attributes = True
