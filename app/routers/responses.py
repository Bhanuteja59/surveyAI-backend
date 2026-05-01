from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.survey import Survey
from app.models.response import Response
from app.models.answer import Answer
from app.models.question import Question
from app.schemas.response import ResponseSubmit, ResponseOut

router = APIRouter(tags=["responses"])


@router.post("/surveys/public/{token}/respond", response_model=ResponseOut, status_code=201)
def submit_response(token: str, payload: ResponseSubmit, request: Request, db: Session = Depends(get_db)):
    from app.models.tenant import Tenant
    survey = db.query(Survey)\
        .join(Tenant, Survey.tenant_id == Tenant.id)\
        .filter(
            Survey.public_token == token,
            Survey.is_published == True,
            Survey.is_active == True,
            Tenant.is_active == True
        ).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    # Validate required questions
    questions = {q.id: q for q in survey.questions}
    answer_map = {a.question_id: a for a in payload.answers}
    for qid, q in questions.items():
        if q.is_required and qid not in answer_map:
            raise HTTPException(status_code=422, detail=f"Question {q.text!r} is required")

    ip = request.client.host if request.client else None
    
    # Prevent duplicate submission based on IP to secure form filling
    if ip:
        existing_response = db.query(Response).filter(
            Response.survey_id == survey.id,
            Response.ip_address == ip
        ).first()
        if existing_response:
            raise HTTPException(status_code=409, detail="You have already completed this survey. Duplicate submissions are not allowed.")

    response = Response(
        survey_id=survey.id,
        tenant_id=survey.tenant_id,
        respondent_name=payload.respondent_name,
        respondent_email=payload.respondent_email,
        ip_address=ip,
    )
    db.add(response)
    db.flush()

    for ans in payload.answers:
        if ans.question_id not in questions:
            continue
        answer = Answer(
            response_id=response.id,
            question_id=ans.question_id,
            tenant_id=survey.tenant_id,
            value=ans.value,
            value_json=ans.value_json,
        )
        db.add(answer)

    db.commit()
    db.refresh(response)

    # Trigger async AI analysis if enough responses
    import logging
    logger = logging.getLogger(__name__)

    try:
        from app.tasks.ai_tasks import run_ai_analysis
        total = db.query(Response).filter(Response.survey_id == survey.id).count()
        if total % 10 == 0 or total == 1:  # analyze on first response and every 10 after
            run_ai_analysis.delay(survey.id)
    except Exception as e:
        logger.warning(f"Could not connect to Redis to queue AI task. Form submitted successfully, but background task skipped. Error: {e}")

    # Trigger Real-Time Webhook for 3rd Party Integrations
    if survey.webhook_url:
        import httpx
        from fastapi import BackgroundTasks
        
        def push_webhook(url: str, secret: str, response_data: dict):
            try:
                headers = {"Content-Type": "application/json"}
                if secret:
                    headers["X-Webhook-Secret"] = secret
                with httpx.Client() as client:
                    client.post(url, json=response_data, headers=headers, timeout=5.0)
            except Exception as e:
                logger.error(f"Failed to push webhook to {url}: {e}")

        # Construct JSON payload for webhook
        out_data = {
            "survey_id": survey.id,
            "survey_title": survey.title,
            "response_id": response.id,
            "respondent_name": response.respondent_name,
            "respondent_email": response.respondent_email,
            "answers": [
                {
                    "question_id": a.question_id,
                    "value": a.value,
                    "value_json": a.value_json
                } for a in payload.answers
            ]
        }
        
        # Fire and forget
        import threading
        t = threading.Thread(target=push_webhook, args=(survey.webhook_url, survey.webhook_secret, out_data))
        t.start()

    return db.query(Response).filter(Response.id == response.id).first()


@router.get("/surveys/{survey_id}/responses", response_model=List[ResponseOut])
def list_responses(survey_id: int, skip: int = 0, limit: int = 50, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    survey = db.query(Survey).filter(Survey.id == survey_id, Survey.tenant_id == current_user.tenant_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    responses = db.query(Response).filter(Response.survey_id == survey_id).order_by(Response.submitted_at.desc()).offset(skip).limit(limit).all()
    return responses
