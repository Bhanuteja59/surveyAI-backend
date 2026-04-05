from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from datetime import datetime, timedelta, timezone
import json
import asyncio
from pydantic import BaseModel
from app.core.database import get_db, SessionLocal
from app.core.deps import require_super_admin
from app.models import User, Tenant, Survey, Response

router = APIRouter(prefix="/superadmin", tags=["superadmin"])

class TenantCreate(BaseModel):
    name: str
    slug: str

def _tenant_stats(tenant_id: int, db: Session) -> dict:
    today = datetime.now(timezone.utc).date()
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    total_surveys = db.query(func.count(Survey.id)).filter(
        Survey.tenant_id == tenant_id, Survey.is_active == True
    ).scalar() or 0
    published = db.query(func.count(Survey.id)).filter(
        Survey.tenant_id == tenant_id, Survey.is_active == True, Survey.is_published == True
    ).scalar() or 0
    total_responses = db.query(func.count(Response.id)).filter(
        Response.tenant_id == tenant_id
    ).scalar() or 0
    today_responses = db.query(func.count(Response.id)).filter(
        Response.tenant_id == tenant_id,
        cast(Response.submitted_at, Date) == today,
    ).scalar() or 0
    week_responses = db.query(func.count(Response.id)).filter(
        Response.tenant_id == tenant_id,
        Response.submitted_at >= week_ago,
    ).scalar() or 0
    user_count = db.query(func.count(User.id)).filter(User.tenant_id == tenant_id).scalar() or 0

    # Get top surveys
    top_surveys = db.query(Survey.title, func.count(Response.id).label('rcount'))\
        .outerjoin(Response, Survey.id == Response.survey_id)\
        .filter(Survey.tenant_id == tenant_id)\
        .group_by(Survey.id)\
        .order_by(func.count(Response.id).desc())\
        .limit(3).all()

    survey_data = [{"title": s[0], "responses": s[1]} for s in top_surveys]

    return {
        "total_surveys": total_surveys,
        "published_surveys": published,
        "total_responses": total_responses,
        "responses_today": today_responses,
        "responses_this_week": week_responses,
        "user_count": user_count,
        "top_surveys": survey_data
    }


def _global_snapshot(db: Session) -> dict:
    tenants = db.query(Tenant).all()
    tenant_list = []
    totals = {"total_responses": 0, "total_surveys": 0, "responses_today": 0, "responses_this_week": 0}

    for t in tenants:
        stats = _tenant_stats(t.id, db)
        for k in totals:
            totals[k] += stats[k]
        tenant_list.append({
            "id": t.id,
            "name": t.name,
            "slug": t.slug,
            "is_active": t.is_active,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            **stats,
        })

    tenant_list.sort(key=lambda x: x["total_responses"], reverse=True)

    # Time-series for chart (last 7 days platform-wide)
    chart_data = []
    for i in range(7):
        day = (datetime.now(timezone.utc) - timedelta(days=6-i)).date()
        c = db.query(func.count(Response.id)).filter(
            cast(Response.submitted_at, Date) == day
        ).scalar() or 0
        chart_data.append({"date": day.strftime("%b %d"), "count": c})

    # Recent Platform Activity
    recent_responses_raw = db.query(Response, Survey, Tenant)\
        .join(Survey, Response.survey_id == Survey.id)\
        .join(Tenant, Response.tenant_id == Tenant.id)\
        .order_by(Response.submitted_at.desc())\
        .limit(10).all()
    
    recent_activity = []
    for resp, surv, t in recent_responses_raw:
        recent_activity.append({
            "id": resp.id,
            "tenant_name": t.name,
            "survey_title": surv.title,
            "time": resp.submitted_at.isoformat() if resp.submitted_at else ""
        })

    return {
        "total_tenants": len(tenants),
        **totals,
        "tenants": tenant_list,
        "chart_data": chart_data,
        "recent_activity": recent_activity,
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/stats")
def global_stats(db: Session = Depends(get_db), _: User = Depends(require_super_admin)):
    return _global_snapshot(db)

@router.post("/tenants")
def create_new_tenant(payload: TenantCreate, db: Session = Depends(get_db), _: User = Depends(require_super_admin)):
    if db.query(Tenant).filter(Tenant.slug == payload.slug).first():
        raise HTTPException(status_code=400, detail="Slug already exists")
    t = Tenant(name=payload.name, slug=payload.slug)
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"id": t.id, "name": t.name, "slug": t.slug}

@router.delete("/tenants/{tenant_id}")
def delete_org(tenant_id: int, db: Session = Depends(get_db), _: User = Depends(require_super_admin)):
    t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    db.delete(t)
    db.commit()
    return {"status": "deleted"}

@router.patch("/tenants/{tenant_id}/toggle")
def toggle_tenant(tenant_id: int, db: Session = Depends(get_db), _: User = Depends(require_super_admin)):
    t = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    t.is_active = not t.is_active
    db.commit()
    db.refresh(t)
    return {"id": t.id, "name": t.name, "is_active": t.is_active}


@router.post("/promote")
def promote(payload: dict, db: Session = Depends(get_db), _: User = Depends(require_super_admin)):
    email = payload.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="email is required")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = "super_admin"
    db.commit()
    return {"id": user.id, "email": user.email, "role": user.role}


@router.get("/tenants/{tenant_id}/surveys")
def get_tenant_surveys(tenant_id: int, db: Session = Depends(get_db), _: User = Depends(require_super_admin)):
    surveys = db.query(Survey).filter(Survey.tenant_id == tenant_id).all()
    res = []
    for s in surveys:
        cnt = db.query(func.count(Response.id)).filter(Response.survey_id == s.id).scalar() or 0
        res.append({
            "id": s.id,
            "title": s.title,
            "public_token": s.public_token,
            "is_active": s.is_active,
            "is_published": s.is_published,
            "response_count": cnt,
            "created_at": s.created_at.isoformat() if s.created_at else None
        })
    return res

@router.delete("/tenants/{tenant_id}/surveys/{survey_id}")
def delete_tenant_survey(tenant_id: int, survey_id: int, db: Session = Depends(get_db), _: User = Depends(require_super_admin)):
    s = db.query(Survey).filter(Survey.id == survey_id, Survey.tenant_id == tenant_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Survey not found")
    db.delete(s)
    db.commit()
    return {"status": "deleted"}

@router.patch("/tenants/{tenant_id}/surveys/{survey_id}/toggle")
def toggle_tenant_survey(tenant_id: int, survey_id: int, db: Session = Depends(get_db), _: User = Depends(require_super_admin)):
    s = db.query(Survey).filter(Survey.id == survey_id, Survey.tenant_id == tenant_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Survey not found")
    s.is_active = not s.is_active
    db.commit()
    return {"status": "toggled", "is_active": s.is_active}


@router.get("/stream")
async def stream(request: Request, _: User = Depends(require_super_admin)):
    async def generator():
        while True:
            if await request.is_disconnected():
                break
            db = SessionLocal()
            try:
                snapshot = _global_snapshot(db)
                yield f"data: {json.dumps(snapshot)}\n\n"
            except Exception:
                yield "data: {}\n\n"
            finally:
                db.close()
            await asyncio.sleep(5)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
