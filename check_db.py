
import sys
import os
from sqlalchemy import create_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

# Add backend to path
sys.path.append(r'd:\next js projects\survey AI\backend')

from app.core.database import SessionLocal, engine
from app.models import Survey, Tenant, User, Response

def check_db():
    db = SessionLocal()
    try:
        tenants = db.query(Tenant).all()
        print(f"Tenants: {len(tenants)}")
        for t in tenants:
            print(f"  - ID: {t.id}, Name: {t.name}, Slug: {t.slug}")

        users = db.query(User).all()
        print(f"Users: {len(users)}")
        for u in users:
            print(f"  - ID: {u.id}, Email: {u.email}, Tenant ID: {u.tenant_id}")

        surveys = db.query(Survey).all()
        print(f"Surveys: {len(surveys)}")
        for s in surveys:
            print(f"  - ID: {s.id}, Title: {s.title}, Tenant ID: {s.tenant_id}, Active: {s.is_active}, Published: {s.is_published}")

        responses = db.query(Response).all()
        print(f"Responses: {len(responses)}")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_db()
