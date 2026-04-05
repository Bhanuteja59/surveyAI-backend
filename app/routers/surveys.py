from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func
from typing import List
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.survey import Survey
from app.models.question import Question
from app.models.response import Response
from app.schemas.survey import SurveyCreate, SurveyUpdate, SurveyOut, SurveyListItem, QuestionCreate, QuestionOut, QuestionUpdate

router = APIRouter(prefix="/surveys", tags=["surveys"])


def _assert_survey_owner(survey: Survey, user: User):
    if survey.tenant_id != user.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")


@router.post("", response_model=SurveyOut, status_code=201)
def create_survey(payload: SurveyCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    import secrets
    survey = Survey(
        tenant_id=current_user.tenant_id,
        created_by=current_user.id,
        title=payload.title,
        description=payload.description,
        public_token=f"{current_user.user_uuid}-{secrets.token_urlsafe(16)}"
    )
    db.add(survey)
    db.flush()

    for q in payload.questions or []:
        question = Question(
            survey_id=survey.id,
            tenant_id=current_user.tenant_id,
            text=q.text,
            question_type=q.question_type,
            options=q.options,
            is_required=q.is_required,
            order_index=q.order_index,
        )
        db.add(question)

    db.commit()
    db.refresh(survey)
    survey = db.query(Survey).options(selectinload(Survey.questions)).filter(Survey.id == survey.id).first()
    response_count = db.query(func.count(Response.id)).filter(Response.survey_id == survey.id).scalar()
    result = SurveyOut.model_validate(survey)
    result.response_count = response_count
    return result


@router.get("", response_model=List[SurveyListItem])
def list_surveys(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    surveys = db.query(Survey).filter(Survey.tenant_id == current_user.tenant_id, Survey.is_active == True).order_by(Survey.created_at.desc()).all()
    result = []
    for s in surveys:
        count = db.query(func.count(Response.id)).filter(Response.survey_id == s.id).scalar()
        item = SurveyListItem.model_validate(s)
        item.response_count = count
        result.append(item)
    return result


@router.get("/{survey_id}", response_model=SurveyOut)
def get_survey(survey_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    survey = db.query(Survey).options(selectinload(Survey.questions)).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    _assert_survey_owner(survey, current_user)
    response_count = db.query(func.count(Response.id)).filter(Response.survey_id == survey.id).scalar()
    result = SurveyOut.model_validate(survey)
    result.response_count = response_count
    return result


@router.patch("/{survey_id}", response_model=SurveyOut)
def update_survey(survey_id: int, payload: SurveyUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    _assert_survey_owner(survey, current_user)
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(survey, field, val)
    db.commit()
    db.refresh(survey)
    survey = db.query(Survey).options(selectinload(Survey.questions)).filter(Survey.id == survey.id).first()
    response_count = db.query(func.count(Response.id)).filter(Response.survey_id == survey.id).scalar()
    result = SurveyOut.model_validate(survey)
    result.response_count = response_count
    return result


@router.delete("/{survey_id}", status_code=204)
def delete_survey(survey_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    _assert_survey_owner(survey, current_user)
    survey.is_active = False
    db.commit()


# ── Questions ──────────────────────────────────────────────────────────────────

@router.post("/{survey_id}/questions", response_model=QuestionOut, status_code=201)
def add_question(survey_id: int, payload: QuestionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    _assert_survey_owner(survey, current_user)
    q = Question(
        survey_id=survey_id,
        tenant_id=current_user.tenant_id,
        text=payload.text,
        question_type=payload.question_type,
        options=payload.options,
        is_required=payload.is_required,
        order_index=payload.order_index,
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return q


@router.patch("/{survey_id}/questions/{question_id}", response_model=QuestionOut)
def update_question(survey_id: int, question_id: int, payload: QuestionUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    _assert_survey_owner(survey, current_user)
    q = db.query(Question).filter(Question.id == question_id, Question.survey_id == survey_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(q, field, val)
    db.commit()
    db.refresh(q)
    return q


@router.delete("/{survey_id}/questions/{question_id}", status_code=204)
def delete_question(survey_id: int, question_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    _assert_survey_owner(survey, current_user)
    q = db.query(Question).filter(Question.id == question_id, Question.survey_id == survey_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    db.delete(q)
    db.commit()


# ── Public survey by token ────────────────────────────────────────────────────

@router.get("/public/{token}", response_model=SurveyOut)
def get_public_survey(token: str, db: Session = Depends(get_db)):
    survey = db.query(Survey).options(selectinload(Survey.questions)).filter(
        Survey.public_token == token,
        Survey.is_published == True,
        Survey.is_active == True,
    ).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found or not published")
    result = SurveyOut.model_validate(survey)
    result.response_count = 0
    return result
