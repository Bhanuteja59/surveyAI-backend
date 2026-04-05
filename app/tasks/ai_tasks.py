import logging
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def run_ai_analysis(self, survey_id: int):
    """Celery task: run AI analysis for a survey asynchronously."""
    try:
        from app.core.database import SessionLocal
        from app.services.ai_service import analyze_survey

        db = SessionLocal()
        try:
            result = analyze_survey(survey_id, db)
            if result:
                logger.info(f"AI analysis completed for survey {survey_id}, insight id={result.id}")
            return {"survey_id": survey_id, "status": "completed"}
        finally:
            db.close()
    except Exception as exc:
        logger.error(f"AI task failed for survey {survey_id}: {exc}")
        raise self.retry(exc=exc)
