from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import ANPREvent, Vehicle
from algorithms.risk_engine import (
    MAX_PLAUSIBLE_KMH,
    build_road_graph,
)


router = APIRouter(
    prefix="/api/movement",
    tags=["Movement"],
)


# =========================================================
# REQUEST MODEL
# =========================================================

class MovementAnalysisRequest(BaseModel):
    registration_number: str

    from_event_id: Optional[str] = None
    to_event_id: Optional[str] = None


# =========================================================
# HELPERS
# =========================================================

def get_event(
    db: Session,
    event_id: str,
):
    return (
        db.query(ANPREvent)
        .filter(ANPREvent.event_id == event_id)
        .first()
    )


def analyze_events(
    from_event: ANPREvent,
    to_event: ANPREvent,
    vehicle: Optional[Vehicle],
):
    # -----------------------------------------------------
    # Chronology
    # -----------------------------------------------------

    if (
        from_event.timestamp is None
        or to_event.timestamp is None
    ):
        return {
            "status": "INSUFFICIENT_DATA",
            "message": "Both events require timestamps.",
        }

    if to_event.timestamp <= from_event.timestamp:
        return {
            "status": "INVALID_SEQUENCE",
            "message": "Destination event must occur after origin event.",
        }

    # -----------------------------------------------------
    # Same location
    # -----------------------------------------------------

    if from_event.location == to_event.location:

        elapsed_seconds = (
            to_event.timestamp - from_event.timestamp
        ).total_seconds()

        elapsed_hours = elapsed_seconds / 3600

        return {
            "status": "MOVEMENT CONSISTENT",
            "from_location": from_event.location,
            "to_location": to_event.location,
            "from_time": from_event.timestamp,
            "to_time": to_event.timestamp,
            "route_distance_km": 0.0,
            "elapsed_hours": round(elapsed_hours, 3),
            "implied_speed_kmh": 0.0,
            "reason": (
                "Both observations occurred at the same gate. "
                "No cross-gate movement anomaly is inferred."
            ),
        }

    # -----------------------------------------------------
    # Graph shortest path
    # -----------------------------------------------------

    graph = build_road_graph()

    distance = graph.shortest_distance(
        from_event.location,
        to_event.location,
    )

    if distance is None:
        return {
            "status": "INSUFFICIENT_DATA",
            "message": (
                f"No route is available in the configured graph "
                f"between {from_event.location} and "
                f"{to_event.location}."
            ),
        }

    # -----------------------------------------------------
    # Travel time
    # -----------------------------------------------------

    elapsed_seconds = (
        to_event.timestamp - from_event.timestamp
    ).total_seconds()

    elapsed_hours = elapsed_seconds / 3600

    if elapsed_hours <= 0:
        return {
            "status": "INVALID_SEQUENCE",
            "message": "Elapsed time must be positive.",
        }

    # -----------------------------------------------------
    # Implied speed
    # -----------------------------------------------------

    implied_speed = distance / elapsed_hours

    # -----------------------------------------------------
    # Vehicle type consistency
    # -----------------------------------------------------

    detected_type_consistent = True

    if (
        from_event.detected_vehicle_type
        and to_event.detected_vehicle_type
    ):
        detected_type_consistent = (
            from_event.detected_vehicle_type.strip().lower()
            == to_event.detected_vehicle_type.strip().lower()
        )

    registry_type_consistent = True

    if vehicle:
        origin_type = (
            from_event.detected_vehicle_type or ""
        ).strip().lower()

        destination_type = (
            to_event.detected_vehicle_type or ""
        ).strip().lower()

        registry_type = (
            vehicle.vehicle_type or ""
        ).strip().lower()

        if origin_type:
            registry_type_consistent = (
                origin_type == registry_type
            )

        if destination_type:
            registry_type_consistent = (
                registry_type_consistent
                and destination_type == registry_type
            )

    # -----------------------------------------------------
    # Movement decision
    # -----------------------------------------------------

    anomaly_reasons = []

    if implied_speed > MAX_PLAUSIBLE_KMH:
        anomaly_reasons.append(
            f"Implied speed {implied_speed:.1f} km/h "
            f"exceeds configured threshold "
            f"of {MAX_PLAUSIBLE_KMH} km/h."
        )

    if not detected_type_consistent:
        anomaly_reasons.append(
            "The two observations report different "
            "vehicle types."
        )

    if not registry_type_consistent:
        anomaly_reasons.append(
            "Observed vehicle type does not match "
            "the registry vehicle type."
        )

    if anomaly_reasons:

        return {
            "status": "MOVEMENT ANOMALY — REQUIRES VERIFICATION",
            "from_location": from_event.location,
            "to_location": to_event.location,
            "from_time": from_event.timestamp,
            "to_time": to_event.timestamp,
            "route_distance_km": round(distance, 2),
            "elapsed_hours": round(elapsed_hours, 3),
            "implied_speed_kmh": round(implied_speed, 1),
            "configured_speed_threshold_kmh": MAX_PLAUSIBLE_KMH,
            "vehicle_type_consistent": (
                detected_type_consistent
            ),
            "registry_type_consistent": (
                registry_type_consistent
            ),
            "reasons": anomaly_reasons,
        }

    return {
        "status": "MOVEMENT CONSISTENT",
        "from_location": from_event.location,
        "to_location": to_event.location,
        "from_time": from_event.timestamp,
        "to_time": to_event.timestamp,
        "route_distance_km": round(distance, 2),
        "elapsed_hours": round(elapsed_hours, 3),
        "implied_speed_kmh": round(implied_speed, 1),
        "configured_speed_threshold_kmh": MAX_PLAUSIBLE_KMH,
        "vehicle_type_consistent": (
            detected_type_consistent
        ),
        "registry_type_consistent": (
            registry_type_consistent
        ),
        "reasons": [],
    }


# =========================================================
# GET VEHICLE MOVEMENT HISTORY
# =========================================================

@router.get("/{registration_number}")
def get_movement_history(
    registration_number: str,
    db: Session = Depends(get_db),
):
    plate = registration_number.strip().upper()

    events = (
        db.query(ANPREvent)
        .filter(
            ANPREvent.registration_number == plate
        )
        .order_by(ANPREvent.timestamp.asc())
        .all()
    )

    if not events:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "No ANPR movement history found",
                "registration_number": plate,
            },
        )

    return {
        "registration_number": plate,
        "event_count": len(events),
        "events": [
            {
                "event_id": event.event_id,
                "location": event.location,
                "camera_id": event.camera_id,
                "timestamp": event.timestamp,
                "detected_vehicle_type": (
                    event.detected_vehicle_type
                ),
                "detected_colour": (
                    event.detected_colour
                ),
                "ocr_confidence": (
                    event.ocr_confidence
                ),
            }
            for event in events
        ],
    }


# =========================================================
# CROSS-GATE ANALYSIS
# =========================================================

@router.post("/analyze")
def analyze_movement(
    request: MovementAnalysisRequest,
    db: Session = Depends(get_db),
):
    plate = request.registration_number.strip().upper()

    # -----------------------------------------------------
    # Registry lookup
    # -----------------------------------------------------

    vehicle = (
        db.query(Vehicle)
        .filter(
            Vehicle.registration_number == plate
        )
        .first()
    )

    # -----------------------------------------------------
    # Select events
    # -----------------------------------------------------

    if request.from_event_id and request.to_event_id:

        from_event = get_event(
            db,
            request.from_event_id,
        )

        to_event = get_event(
            db,
            request.to_event_id,
        )

        if from_event is None or to_event is None:
            raise HTTPException(
                status_code=404,
                detail="One or both event IDs were not found.",
            )

    else:

        events = (
            db.query(ANPREvent)
            .filter(
                ANPREvent.registration_number == plate
            )
            .order_by(ANPREvent.timestamp.desc())
            .limit(2)
            .all()
        )

        if len(events) < 2:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": (
                        "At least two ANPR events are required "
                        "for cross-gate analysis."
                    ),
                    "registration_number": plate,
                    "event_count": len(events),
                },
            )

        to_event = events[0]
        from_event = events[1]

    # -----------------------------------------------------
    # Protect against mismatched plates
    # -----------------------------------------------------

    if (
        from_event.registration_number.strip().upper()
        != plate
        or to_event.registration_number.strip().upper()
        != plate
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Both events must belong to the requested "
                "registration number."
            ),
        )

    result = analyze_events(
        from_event,
        to_event,
        vehicle,
    )

    return {
        "registration_number": plate,
        "registry_match": vehicle is not None,
        "vehicle": (
            {
                "vehicle_id": vehicle.vehicle_id,
                "vehicle_type": vehicle.vehicle_type,
                "registered_colour": (
                    vehicle.registered_colour
                ),
                "operator": vehicle.operator,
            }
            if vehicle
            else None
        ),
        "origin_event": {
            "event_id": from_event.event_id,
            "location": from_event.location,
            "timestamp": from_event.timestamp,
            "vehicle_type": (
                from_event.detected_vehicle_type
            ),
        },
        "destination_event": {
            "event_id": to_event.event_id,
            "location": to_event.location,
            "timestamp": to_event.timestamp,
            "vehicle_type": (
                to_event.detected_vehicle_type
            ),
        },
        "analysis": result,
    }
