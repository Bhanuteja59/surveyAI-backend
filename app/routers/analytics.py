from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from typing import List
from datetime import datetime, timedelta, timezone
import json
import asyncio
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.survey import Survey
from app.models.question import Question
from app.models.response import Response
from app.models.answer import Answer
from app.schemas.analytics import SurveyAnalytics, QuestionAnalytics, TrendPoint, DashboardStats

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _build_survey_analytics(survey_id: int, tenant_id: int, db: Session) -> SurveyAnalytics:
    survey = db.query(Survey).filter(Survey.id == survey_id, Survey.tenant_id == tenant_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    total = db.query(func.count(Response.id)).filter(Response.survey_id == survey_id).scalar() or 0
    today = datetime.now(timezone.utc).date()
    responses_today = db.query(func.count(Response.id)).filter(
        Response.survey_id == survey_id,
        cast(Response.submitted_at, Date) == today
    ).scalar() or 0
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    responses_week = db.query(func.count(Response.id)).filter(
        Response.survey_id == survey_id,
        Response.submitted_at >= week_ago,
    ).scalar() or 0

    # Trend: last 14 days
    trend_points = []
    for i in range(13, -1, -1):
        day = today - timedelta(days=i)
        count = db.query(func.count(Response.id)).filter(
            Response.survey_id == survey_id,
            cast(Response.submitted_at, Date) == day,
        ).scalar() or 0
        trend_points.append(TrendPoint(date=day.isoformat(), count=count))

    # Per-question analytics
    questions = db.query(Question).filter(Question.survey_id == survey_id).order_by(Question.order_index).all()
    q_analytics = []
    for q in questions:
        answers = db.query(Answer).filter(Answer.question_id == q.id).all()
        total_answers = len(answers)

        if q.question_type in ("multiple_choice", "dropdown"):
            dist: dict = {}
            for a in answers:
                key = a.value or "No answer"
                dist[key] = dist.get(key, 0) + 1
            q_analytics.append(QuestionAnalytics(
                question_id=q.id,
                question_text=q.text,
                question_type=q.question_type,
                total_answers=total_answers,
                choice_distribution=dist,
            ))

        elif q.question_type == "rating":
            values = [int(a.value) for a in answers if a.value and a.value.isdigit()]
            avg = round(sum(values) / len(values), 2) if values else 0.0
            dist = {}
            for v in values:
                dist[str(v)] = dist.get(str(v), 0) + 1
            q_analytics.append(QuestionAnalytics(
                question_id=q.id,
                question_text=q.text,
                question_type=q.question_type,
                total_answers=total_answers,
                avg_rating=avg,
                rating_distribution=dist,
            ))

        elif q.question_type == "text_input":
            samples = [a.value for a in answers if a.value][:10]
            q_analytics.append(QuestionAnalytics(
                question_id=q.id,
                question_text=q.text,
                question_type=q.question_type,
                total_answers=total_answers,
                sample_responses=samples,
            ))

    return SurveyAnalytics(
        survey_id=survey.id,
        survey_title=survey.title,
        total_responses=total,
        responses_today=responses_today,
        responses_this_week=responses_week,
        completion_trend=trend_points,
        question_analytics=q_analytics,
    )


def _build_dashboard_stats(db: Session, tid: int) -> DashboardStats:
    total_surveys = db.query(func.count(Survey.id)).filter(Survey.tenant_id == tid, Survey.is_active == True).scalar() or 0
    published = db.query(func.count(Survey.id)).filter(Survey.tenant_id == tid, Survey.is_active == True, Survey.is_published == True).scalar() or 0
    total_responses = db.query(func.count(Response.id)).filter(Response.tenant_id == tid).scalar() or 0
    today = datetime.now(timezone.utc).date()
    today_responses = db.query(func.count(Response.id)).filter(
        Response.tenant_id == tid,
        cast(Response.submitted_at, Date) == today,
    ).scalar() or 0
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    week_responses = db.query(func.count(Response.id)).filter(
        Response.tenant_id == tid,
        Response.submitted_at >= week_ago,
    ).scalar() or 0

    recent_surveys = db.query(Survey).filter(Survey.tenant_id == tid, Survey.is_active == True).order_by(Survey.created_at.desc()).limit(5).all()
    recent_list = []
    for s in recent_surveys:
        cnt = db.query(func.count(Response.id)).filter(Response.survey_id == s.id).scalar() or 0
        recent_list.append({"id": s.id, "title": s.title, "response_count": cnt, "is_published": s.is_published})

    trend_points = []
    for i in range(13, -1, -1):
        day = today - timedelta(days=i)
        count = db.query(func.count(Response.id)).filter(
            Response.tenant_id == tid,
            cast(Response.submitted_at, Date) == day,
        ).scalar() or 0
        trend_points.append(TrendPoint(date=day.isoformat(), count=count))

    recent_responses = db.query(Response, Survey)\
        .join(Survey, Response.survey_id == Survey.id)\
        .filter(Response.tenant_id == tid)\
        .order_by(Response.submitted_at.desc()).limit(15).all()
    
    recent_activity = []
    for resp, surv in recent_responses:
        recent_activity.append({
            "id": resp.id,
            "survey_title": surv.title,
            "time": resp.submitted_at.isoformat() if resp.submitted_at else ""
        })

    return DashboardStats(
        total_surveys=total_surveys,
        published_surveys=published,
        total_responses=total_responses,
        responses_today=today_responses,
        responses_this_week=week_responses,
        recent_surveys=recent_list,
        completion_trend=trend_points,
        recent_activity=recent_activity
    )

@router.get("/dashboard", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _build_dashboard_stats(db, current_user.tenant_id)


from app.core.database import SessionLocal

@router.get("/dashboard/stream")
async def stream_dashboard(request: Request, current_user: User = Depends(get_current_user)):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            db = SessionLocal()
            try:
                data = _build_dashboard_stats(db, current_user.tenant_id)
                yield f"data: {data.model_dump_json()}\n\n"
            except Exception:
                yield "data: {}\n\n"
            finally:
                db.close()
            await asyncio.sleep(5)

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/surveys/{survey_id}", response_model=SurveyAnalytics)
def survey_analytics(survey_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _build_survey_analytics(survey_id, current_user.tenant_id, db)


@router.get("/surveys/{survey_id}/stream")
async def stream_analytics(survey_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Server-Sent Events endpoint for real-time analytics updates."""
    survey = db.query(Survey).filter(Survey.id == survey_id, Survey.tenant_id == current_user.tenant_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                data = _build_survey_analytics(survey_id, current_user.tenant_id, db)
                yield f"data: {data.model_dump_json()}\n\n"
            except Exception:
                yield "data: {}\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
