from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI

from backend.database import Base, engine
from backend.api.vehicles import router as vehicle_router
from backend.api.anpr import router as anpr_router
from backend.api.movement import router as movement_router
from backend.api.fastag import router as fastag_router
from backend.api.correlation import router as correlation_router
from backend.api.risk import router as risk_router
from backend.api.reports import router as reports_router
from backend.api.audit import router as audit_router

app = FastAPI(
    title="TRUSTRAK AI API",
    description="Commercial Vehicle Integrity & Verification Backend",
    version="1.0.0",
)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"

app.mount(
    "/ui",
    StaticFiles(
        directory=FRONTEND_DIR,
        html=True,
    ),
    name="frontend",
)


# =========================================================
# DATABASE
# =========================================================

Base.metadata.create_all(bind=engine)


# =========================================================
# API ROUTERS
# =========================================================

app.include_router(vehicle_router)
app.include_router(anpr_router)
app.include_router(movement_router)
app.include_router(fastag_router)
app.include_router(correlation_router)
app.include_router(risk_router)
app.include_router(reports_router)
app.include_router(audit_router)


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():
    return {
        "system": "TRUSTRAK AI",
        "status": "online",
        "version": "1.0.0",
    }


# =========================================================
# HEALTH
# =========================================================

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "TRUSTRAK AI backend",
        "database": "connected",
    }