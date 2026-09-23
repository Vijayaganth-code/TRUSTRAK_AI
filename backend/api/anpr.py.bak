from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import (
    ANPREvent,
    Vehicle,
    VerificationCase,
)

from backend.services.live_risk import evaluate_live_risk
from algorithms.risk_engine import MaxHeap


router = APIRouter(
    prefix="/api/anpr",
    tags=["ANPR"],
)


class ANPREventCreate(BaseModel):
    registration_number: str = Field(min_length=1)
    camera_id: str = Field(min_length=1)
    location: str = Field(min_length=1)

    timestamp: datetime | None = None

    detected_vehicle_type: str | None = None
    detected_colour: str | None = None

    ocr_confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    event_type: str = "NORMAL"


@router.post("/events")
def create_anpr_event(
    event_data: ANPREventCreate,
    db: Session = Depends(get_db),
):
    plate = event_data.registration_number.strip().upper()

    # Registry lookup
    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.registration_number == plate)
        .first()
    )

    # Find the latest event
    last_event = (
        db.query(ANPREvent)
        .order_by(ANPREvent.id.desc())
        .first()
    )

    if last_event is None:
        next_number = 1
    else:
        try:
            next_number = int(
                last_event.event_id.split("-")[-1]
            ) + 1
        except (ValueError, AttributeError):
            next_number = last_event.id + 1

    event_id = f"ANPR-{next_number:06d}"

    event_timestamp = (
        event_data.timestamp
        if event_data.timestamp is not None
        else datetime.now()
    )

    event_type = event_data.event_type.strip().upper()

    # Unknown registration is explicitly represented.
    if vehicle is None:
        event_type = "UNKNOWN_REGISTRY"

    event = ANPREvent(
        event_id=event_id,
        registration_number=plate,
        camera_id=event_data.camera_id.strip().upper(),
        location=event_data.location.strip(),
        timestamp=event_timestamp,
        detected_vehicle_type=(
            event_data.detected_vehicle_type.strip()
            if event_data.detected_vehicle_type
            else None
        ),
        detected_colour=(
            event_data.detected_colour.strip()
            if event_data.detected_colour
            else None
        ),
        ocr_confidence=event_data.ocr_confidence,
        event_type=event_type,
    )

    db.add(event)

    try:
        db.commit()
        db.refresh(event)

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Unable to save ANPR event",
        )

    # -----------------------------------------------------
    # LIVE RISK EVALUATION
    # -----------------------------------------------------

    try:
        live_risk = evaluate_live_risk(
            db,
            plate,
            event.event_id,
        )

        verification_case = (
            update_live_verification_case(
                db,
                live_risk,
            )
        )

    except Exception as error:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "ANPR event saved, but live "
                f"risk evaluation failed: {error}"
            ),
        )

    return {
        "success": True,
        "event": {
            "event_id": event.event_id,
            "registration_number": event.registration_number,
            "camera_id": event.camera_id,
            "location": event.location,
            "timestamp": event.timestamp,
            "detected_vehicle_type": event.detected_vehicle_type,
            "detected_colour": event.detected_colour,
            "ocr_confidence": event.ocr_confidence,
            "event_type": event.event_type,
        },
        "registry_match": vehicle is not None,
        "vehicle": (
            {
                "vehicle_id": vehicle.vehicle_id,
                "registration_number": vehicle.registration_number,
                "vehicle_type": vehicle.vehicle_type,
                "registered_colour": vehicle.registered_colour,
                "operator": vehicle.operator,
                "permit_status": vehicle.permit_status,
                "fitness_status": vehicle.fitness_status,
                "fastag_id": vehicle.fastag_id,
                "fastag_status": vehicle.fastag_status,
            }
            if vehicle
            else None
        ),
        "risk_analysis": {
            "risk_score": live_risk[
                "risk_score"
            ],
            "risk_tier": live_risk[
                "risk_tier"
            ],
            "status": live_risk[
                "status"
            ],
            "reasons": live_risk.get(
                "reasons",
                [],
            ),
            "evidence": live_risk.get(
                "evidence",
                [],
            ),
        },
        "movement_analysis": live_risk.get(
            "movement"
        ),
        "fastag_correlation": live_risk.get(
            "fastag"
        ),
        "verification_case": (
            {
                "case_id": (
                    verification_case.case_id
                ),
                "rank": (
                    verification_case.rank
                ),
                "risk_score": (
                    verification_case.risk_score
                ),
                "risk_tier": (
                    verification_case.risk_tier
                ),
                "status": (
                    verification_case.status
                ),
            }
            if verification_case
            else None
        ),
    }


@router.get("/events")
def get_anpr_events(
    limit: int = 50,
    db: Session = Depends(get_db),
):
    limit = max(1, min(limit, 500))

    events = (
        db.query(ANPREvent)
        .order_by(ANPREvent.timestamp.desc())
        .limit(limit)
        .all()
    )

    return {
        "count": len(events),
        "events": [
            {
                "event_id": event.event_id,
                "registration_number": event.registration_number,
                "camera_id": event.camera_id,
                "location": event.location,
                "timestamp": event.timestamp,
                "detected_vehicle_type": event.detected_vehicle_type,
                "detected_colour": event.detected_colour,
                "ocr_confidence": event.ocr_confidence,
                "event_type": event.event_type,
            }
            for event in events
        ],
    }


def update_live_verification_case(
    db: Session,
    risk_result: dict,
):
    registration_number = risk_result[
        "registration_number"
    ]

    risk_score = risk_result[
        "risk_score"
    ]

    # No case is needed for a normal event.
    if risk_score <= 0:
        return None

    reasons = risk_result.get(
        "reasons",
        [],
    )

    evidence = risk_result.get(
        "evidence",
        [],
    )

    case = (
        db.query(VerificationCase)
        .filter(
            VerificationCase.registration_number
            == registration_number
        )
        .first()
    )

    if case is None:

        # Find the next case number.
        last_case = (
            db.query(VerificationCase)
            .order_by(
                VerificationCase.id.desc()
            )
            .first()
        )

        if last_case is None:
            next_number = 1
        else:
            try:
                next_number = (
                    int(
                        last_case.case_id
                        .split("-")[-1]
                    )
                    + 1
                )
            except (
                ValueError,
                AttributeError,
            ):
                next_number = last_case.id + 1

        case = VerificationCase(
            case_id=(
                f"TR-2026-{next_number:05d}"
            ),
            registration_number=(
                registration_number
            ),
        )

        db.add(case)

    case.risk_score = risk_score
    case.risk_tier = risk_result[
        "risk_tier"
    ]
    case.status = risk_result[
        "status"
    ]
    case.reasons = " | ".join(
        reasons
    )
    case.evidence = " | ".join(
        evidence
    )

    db.flush()

    # -----------------------------------------------------
    # MAX HEAP PRIORITIZATION
    # -----------------------------------------------------

    cases = (
        db.query(VerificationCase)
        .all()
    )

    priority_queue = MaxHeap()

    for current_case in cases:
        priority_queue.push(
            current_case.risk_score or 0,
            current_case.registration_number,
        )

    rank_map = {}

    rank = 1

    while len(priority_queue):

        result = priority_queue.pop()

        if result is None:
            break

        score, plate = result

        rank_map[plate] = rank

        rank += 1

    for current_case in cases:
        current_case.rank = rank_map.get(
            current_case.registration_number
        )

    db.commit()
    db.refresh(case)

    return case

