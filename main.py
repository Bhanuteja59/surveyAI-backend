from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import Base, engine
from app.routers import auth, surveys, responses, analytics, ai, superadmin
import app.models
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("survey_ai")

app = FastAPI(
    title="SurveyAI",
    description="AI-powered multi-tenant survey platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

@app.on_event("startup")
def startup_db_check():
    logger.info("Initializing database...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        if not settings.DEBUG:
            import sys
            sys.exit(1)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
app.include_router(superadmin.router, prefix=API)


@app.get("/")
def root():
    return {"message": "SurveyAI API", "docs": "/docs"}
   

@app.get("/health")
def health():
    return {"status": "ok!"}


#done raaa 