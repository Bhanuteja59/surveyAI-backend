"""
AI service — survey analysis + streaming question generation.
"""
from __future__ import annotations
import json
import logging
from typing import Generator, Optional
from openai import OpenAI
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.survey import Survey
from app.models.question import Question
from app.models.response import Response
from app.models.answer import Answer
from app.models.ai_insight import AIInsight

logger = logging.getLogger(__name__)

# ── Shared clients (created once, reused across requests) ─────────────────────

_groq_client: Optional[OpenAI] = None
_openai_client: Optional[OpenAI] = None


def _groq() -> Optional[OpenAI]:
    global _groq_client
    if _groq_client is None and settings.GROQ_API_KEY:
        _groq_client = OpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
            timeout=15.0,   # hard ceiling — default SDK timeout is 600 s (hangs forever)
            max_retries=0,
        )
    return _groq_client


def _openai() -> Optional[OpenAI]:
    global _openai_client
    if _openai_client is None and settings.OPENAI_API_KEY:
        _openai_client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=15.0,
            max_retries=0,
        )
    return _openai_client


def get_client(use_groq: bool = True):
    """Return (client, model_name) for the best available provider."""
    if use_groq:
        c = _groq()
        if c:
            return c, "llama-3.1-8b-instant"
    c = _openai()
    if c:
        return c, "gpt-4o-mini"
    return None, None


# ── Survey-response analysis (existing feature) ───────────────────────────────

def _build_analysis_prompt(survey: Survey, questions: list, responses: list, answers_by_response: dict) -> str:
    lines = [
        f"Survey Title: {survey.title}",
        f"Description: {survey.description or 'No description'}",
        f"Total Responses: {len(responses)}",
        "",
        "Data Summary per Question:",
    ]
    
    for q in questions:
        lines.append(f"\n- Question: {q.text} (Type: {q.question_type})")
        answers = []
        for resp in responses:
            for ans in answers_by_response.get(resp.id, []):
                if ans.question_id == q.id:
                    val = ans.value or (json.dumps(ans.value_json) if ans.value_json else "No answer")
                    answers.append(val)
        
        if answers:
            # Grouping answers for brevity if possible, or just listing them
            lines.append(f"  Answers: {', '.join(map(str, answers[:50]))}") # limit to 50 for prompt length
            if len(answers) > 50:
                lines.append(f"  ...and {len(answers) - 50} more answers.")
        else:
            lines.append("  No answers recorded for this question.")

    lines += [
        "",
        "Act as an expert survey analyst. Analyze the data above and provide:",
        "1. overall_sentiment: (positive, negative, neutral, or mixed)",
        "2. sentiment_score: a value between 0 and 1 representing sentiment strength.",
        "3. summary: A 2-3 sentence overview of the survey findings.",
        "4. key_insights: A list of the most important takeaways from the responses.",
        "5. suggestions: Actionable advice for the survey creator based on these responses.",
        "6. question_insights: A list of objects with {'question_id': id, 'insight': string} for important questions.",
        "",
        "IMPORTANT: Return ONLY a valid JSON object. No markdown, no extra text.",
    ]
    return "\n".join(lines)


def analyze_survey(survey_id: int, db: Session) -> Optional[AIInsight]:
    if not settings.OPENAI_API_KEY and not settings.GROQ_API_KEY:
        logger.warning("AI API keys not set — skipping analysis")
        return None

    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        return None

    questions = db.query(Question).filter(Question.survey_id == survey_id).order_by(Question.order_index).all()
    responses = db.query(Response).filter(Response.survey_id == survey_id).all()
    
    if not responses:
        logger.info(f"No responses for survey {survey_id} — skipping analysis")
        return None

    response_ids = [r.id for r in responses]
    all_answers = db.query(Answer).filter(Answer.response_id.in_(response_ids)).all()
    answers_by_response: dict = {}
    for ans in all_answers:
        answers_by_response.setdefault(ans.response_id, []).append(ans)

    prompt = _build_analysis_prompt(survey, questions, responses, answers_by_response)

    insight = db.query(AIInsight).filter(AIInsight.survey_id == survey_id).order_by(AIInsight.generated_at.desc()).first()
    if not insight or insight.status == "completed":
        insight = AIInsight(
            survey_id=survey_id, 
            tenant_id=survey.tenant_id, 
            status="processing",
            total_responses_analyzed=len(responses)
        )
        db.add(insight)
    else:
        insight.status = "processing"
        insight.total_responses_analyzed = len(responses)
    db.commit()

    try:
        # Prioritize OpenAI as requested
        client = _openai()
        model = "gpt-4o-mini"
        
        if not client:
            # Fallback to Groq if OpenAI not configured
            client = _groq()
            model = "llama-3.3-70b-versatile"
        
        if not client:
            raise ValueError("No AI client configured (OpenAI or Groq)")

        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a survey analytics expert. You provide deep, actionable insights from raw survey data. Return strictly JSON."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=2000,
        )
        
        raw_content = completion.choices[0].message.content.strip()
        data = json.loads(raw_content)

        insight.overall_sentiment = data.get("overall_sentiment", "neutral")
        insight.sentiment_score = str(data.get("sentiment_score", "0.5"))
        insight.summary = data.get("summary", "Analysis completed.")
        insight.key_insights = data.get("key_insights", [])
        insight.suggestions = data.get("suggestions", [])
        insight.question_insights = data.get("question_insights", [])
        insight.status = "completed"

    except Exception as e:
        logger.error(f"AI analysis failed for survey {survey_id}: {e}")
        insight.status = "failed"
        insight.error_message = str(e)

    db.commit()
    db.refresh(insight)
    return insight


def generate_survey_questions(prompt: str, num_questions: int) -> dict:
    """
    Generate survey questions and return the JSON response immediately.
    """
    client, model = get_client(use_groq=True)
    if not client:
        raise ValueError("AI service is not configured. Add GROQ_API_KEY or OPENAI_API_KEY to .env.")

    system_msg = (
        "You are an expert survey generator. Return ONLY a valid JSON object. "
        "The JSON must have three keys: 'title' (string), 'description' (string), and 'questions' (array of objects). "
        "Questions MUST be categorical (multiple_choice, dropdown, rating). Avoid text_input. "
        "Each question object must be: {'text': string, 'question_type': string, 'is_required': boolean, 'options': object}. "
        "For 'multiple_choice' or 'dropdown', 'options' format: {'choices': ['A', 'B', 'C']}. "
        "For 'rating', 'options' format: {'min': 1, 'max': 5, 'labels': {'1': 'Low', '5': 'High'}}."
    )

    user_msg = f"Create a survey with exactly {num_questions} questions about: {prompt}"

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user",   "content": user_msg},
            ],
            response_format={"type": "json_object"},
            temperature=0.5,
            max_tokens=2000,
            stream=False,
        )

        raw = completion.choices[0].message.content.strip()
        data = json.loads(raw)
        
        # Enforce categorical mapping just to be perfectly safe
        for q in data.get("questions", []):
            if q.get("question_type") == "text_input":
                q["question_type"] = "multiple_choice"
                q.setdefault("options", {}).setdefault("choices", ["Yes", "No", "N/A"])

        return data

    except Exception as e:
        logger.error("generate_survey_questions failed: %s", e)
        raise ValueError(f"Generation failed: {str(e)}")
