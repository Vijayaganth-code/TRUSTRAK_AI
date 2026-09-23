from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import (
    ANPREvent,
    FASTagEvent,
    MovementEvent,
    Vehicle,
    VerificationCase,
)


router = APIRouter(
    prefix="/api/reports",
    tags=["Reports & Analytics"],
)


@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
):
    vehicles = db.query(Vehicle).all()
    anpr_events = db.query(ANPREvent).all()
    fastag_events = db.query(FASTagEvent).all()
    movement_events = db.query(MovementEvent).all()
    cases = db.query(VerificationCase).all()

    risk_counts = {
        "CRITICAL": 0,
        "HIGH": 0,
        "MEDIUM": 0,
        "LOW": 0,
    }

    status_counts = {}

    movement_anomalies = 0
    unknown_registry_events = 0

    for case in cases:
        tier = (
            case.risk_tier.strip().upper()
            if case.risk_tier
            else "LOW"
        )

        if tier in risk_counts:
            risk_counts[tier] += 1

        status = (
            case.status.strip().upper()
            if case.status
            else "UNKNOWN"
        )

        status_counts[status] = (
            status_counts.get(status, 0) + 1
        )

    for event in anpr_events:
        event_type = (
            event.event_type.strip().upper()
            if event.event_type
            else ""
        )

        if event_type == "UNKNOWN_REGISTRY":
            unknown_registry_events += 1

    for movement in movement_events:
        status = (
            movement.movement_status.strip().upper()
            if movement.movement_status
            else ""
        )

        if "ANOMALY" in status:
            movement_anomalies += 1

    open_cases = sum(
        1
        for case in cases
        if case.status
        and case.status.strip().upper()
        in {
            "VERIFY",
            "UNDER_REVIEW",
        }
    )

    return {
        "success": True,
        "generated_at": datetime.now().isoformat(),
        "totals": {
            "vehicles": len(vehicles),
            "anpr_events": len(anpr_events),
            "fastag_events": len(fastag_events),
            "movement_events": len(movement_events),
            "verification_cases": len(cases),
            "open_verification_cases": open_cases,
        },
        "anomalies": {
            "movement_anomalies": movement_anomalies,
            "unknown_registry_events": (
                unknown_registry_events
            ),
        },
        "risk_distribution": risk_counts,
        "verification_status": status_counts,
    }