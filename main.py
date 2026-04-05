from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import Base, engine
from app.routers import auth, surveys, responses, analytics, ai
import app.models  # Ensures all models are registered with Base metadata

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SurveyAI",
    description="AI-powered multi-tenant survey platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API = settings.API_V1_STR  # /api/v1

app.include_router(auth.router, prefix=API)
app.include_router(surveys.router, prefix=API)
app.include_router(responses.router, prefix=API)
app.include_router(analytics.router, prefix=API)
app.include_router(ai.router, prefix=API)


@app.get("/")
def root():
    return {"message": "SurveyAI API", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}
