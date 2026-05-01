from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.survey import Survey
from app.models.ai_insight import AIInsight
from app.schemas.ai_insight import AIInsightOut, AIGenerateRequest
from app.services.ai_service import generate_survey_questions

router = APIRouter(prefix="/ai", tags=["ai"])


# ── Survey-response analysis ──────────────────────────────────────────────────

@router.post("/surveys/{survey_id}/analyze", status_code=202)
def trigger_analysis(
    survey_id: int,
    sync: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    survey = db.query(Survey).filter(
        Survey.id == survey_id,
        Survey.tenant_id == current_user.tenant_id,
    ).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    if sync:
        from app.services.ai_service import analyze_survey
        insight = analyze_survey(survey_id, db)
        if not insight:
            raise HTTPException(status_code=500, detail="AI analysis failed")
        return insight

    from app.tasks.ai_tasks import run_ai_analysis
    task = run_ai_analysis.delay(survey_id)
    return {"message": "AI analysis queued", "task_id": task.id}


@router.get("/surveys/{survey_id}/insights", response_model=List[AIInsightOut])
def get_insights(
    survey_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    survey = db.query(Survey).filter(
        Survey.id == survey_id,
        Survey.tenant_id == current_user.tenant_id,
    ).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    return (
        db.query(AIInsight)
        .filter(AIInsight.survey_id == survey_id)
        .order_by(AIInsight.generated_at.desc())
        .limit(5)
        .all()
    )


@router.get("/surveys/{survey_id}/insights/latest", response_model=AIInsightOut)
def get_latest_insight(
    survey_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    survey = db.query(Survey).filter(
        Survey.id == survey_id,
        Survey.tenant_id == current_user.tenant_id,
    ).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    insight = (
        db.query(AIInsight)
        .filter(AIInsight.survey_id == survey_id)
        .order_by(AIInsight.generated_at.desc())
        .first()
    )
    if not insight:
        raise HTTPException(status_code=404, detail="No insights generated yet")
    return insight


@router.post("/generate")
def generate_survey(
    request: AIGenerateRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Generate survey questions via AI and return JSON immediately.
    """
    try:
        data = generate_survey_questions(request.prompt, request.num_questions)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
