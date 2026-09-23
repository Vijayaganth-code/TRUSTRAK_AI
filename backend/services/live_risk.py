from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.models import (
    ANPREvent,
    FASTagEvent,
    MovementEvent,
    Vehicle,
)
from algorithms.risk_engine import (
    MAX_PLAUSIBLE_KMH,
    SLIDING_WINDOW_HOURS,
    build_road_graph,
)


ROAD_GRAPH = build_road_graph()


def normalize(value):
    if value is None:
        return ""

    return str(value).strip().upper()


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_latest_anpr_events(
    db: Session,
    registration_number: str,
    limit: int = 10,
):
    return (
        db.query(ANPREvent)
        .filter(
            ANPREvent.registration_number
            == registration_number
        )
        .order_by(
            ANPREvent.timestamp.desc()
        )
        .limit(limit)
        .all()
    )


def get_recent_fastag_events(
    db: Session,
    registration_number: str,
    reference_time: datetime,
):
    start_time = (
        reference_time
        - timedelta(
            minutes=60
        )
    )


    return (
        db.query(FASTagEvent)
        .filter(
            FASTagEvent.registration_number
            == registration_number,
            FASTagEvent.timestamp >= start_time,
            FASTagEvent.timestamp <= reference_time,
        )
        .order_by(
            FASTagEvent.timestamp.desc()
        )
        .all()
    )


def calculate_graph_distance(
    origin: str,
    destination: str,
):
    origin = normalize(origin).title()
    destination = normalize(destination).title()

    if origin == destination:
        return 0.0, [origin]

    try:
        distance, path = ROAD_GRAPH.shortest_path(
            origin,
            destination,
        )

        return float(distance), path

    except Exception:
        return None, []


def analyze_latest_movement(
    db: Session,
    registration_number: str,
    latest_anpr: ANPREvent,
):
    events = get_latest_anpr_events(
        db,
        registration_number,
        limit=20,
    )

    if len(events) < 2:
        return {
            "status": "INSUFFICIENT_HISTORY",
            "distance_km": 0.0,
            "elapsed_hours": 0.0,
            "implied_speed_kmh": 0.0,
            "origin": None,
            "destination": None,
            "path": [],
            "reason": "Insufficient ANPR history",
        }

    previous = None

    for event in events:
        if event.id != latest_anpr.id:
            previous = event
            break

    if previous is None:
        return {
            "status": "INSUFFICIENT_HISTORY",
            "distance_km": 0.0,
            "elapsed_hours": 0.0,
            "implied_speed_kmh": 0.0,
            "origin": None,
            "destination": None,
            "path": [],
            "reason": "No previous ANPR event",
        }

    if normalize(previous.location) == normalize(
        latest_anpr.location
    ):
        return {
            "status": "MOVEMENT CONSISTENT",
            "distance_km": 0.0,
            "elapsed_hours": max(
                (
                    latest_anpr.timestamp
                    - previous.timestamp
                ).total_seconds()
                / 3600.0,
                0.0,
            ),
            "implied_speed_kmh": 0.0,
            "origin": previous.location,
            "destination": latest_anpr.location,
            "path": [latest_anpr.location],
            "reason": "Same location",
        }

    distance, path = calculate_graph_distance(
        previous.location,
        latest_anpr.location,
    )

    if distance is None:
        return {
            "status": "INSUFFICIENT_GRAPH_DATA",
            "distance_km": 0.0,
            "elapsed_hours": 0.0,
            "implied_speed_kmh": 0.0,
            "origin": previous.location,
            "destination": latest_anpr.location,
            "path": [],
            "reason": "Locations not found in road graph",
        }

    elapsed_hours = max(
        (
            latest_anpr.timestamp
            - previous.timestamp
        ).total_seconds()
        / 3600.0,
        0.000001,
    )

    implied_speed = distance / elapsed_hours

    reasons = []

    if implied_speed > MAX_PLAUSIBLE_KMH:
        reasons.append(
            "Movement anomaly: "
            f"{previous.location} to "
            f"{latest_anpr.location}, "
            f"{distance:.0f} km in "
            f"{elapsed_hours:.2f} hours "
            f"({implied_speed:.1f} km/h)"
        )

    previous_type = normalize(
        previous.detected_vehicle_type
    )
    latest_type = normalize(
        latest_anpr.detected_vehicle_type
    )

    if (
        previous_type
        and latest_type
        and previous_type != latest_type
    ):
        reasons.append(
            "Vehicle type inconsistency between "
            "ANPR observations"
        )

    if reasons:
        return {
            "status": (
                "MOVEMENT ANOMALY — "
                "REQUIRES VERIFICATION"
            ),
            "distance_km": round(
                distance,
                2,
            ),
            "elapsed_hours": round(
                elapsed_hours,
                3,
            ),
            "implied_speed_kmh": round(
                implied_speed,
                2,
            ),
            "origin": previous.location,
            "destination": latest_anpr.location,
            "path": path,
            "reason": " | ".join(reasons),
        }

    return {
        "status": "MOVEMENT CONSISTENT",
        "distance_km": round(
            distance,
            2,
        ),
        "elapsed_hours": round(
            elapsed_hours,
            3,
        ),
        "implied_speed_kmh": round(
            implied_speed,
            2,
        ),
        "origin": previous.location,
        "destination": latest_anpr.location,
        "path": path,
        "reason": "Plausible travel time",
    }


def find_best_fastag_match(
    db: Session,
    vehicle: Vehicle,
    latest_anpr: ANPREvent,
):
    events = get_recent_fastag_events(
        db,
        vehicle.registration_number,
        latest_anpr.timestamp,
    )

    best = None
    best_delta = None

    for event in events:

        delta_seconds = (
            latest_anpr.timestamp
            - event.timestamp
        ).total_seconds()

        delta_minutes = (
            abs(delta_seconds)
            / 60.0
        )

        same_location = (
            normalize(event.toll_plaza)
            .find(
                normalize(latest_anpr.location)
            )
            >= 0
        )

        score = 0

        if event.registration_number == latest_anpr.registration_number:
            score += 1

        if event.fastag_id == vehicle.fastag_id:
            score += 1

        if same_location:
            score += 1

        if event.transaction_status == "SUCCESS":
            score += 1

        if delta_minutes <= 60:
            score += 1

        if (
            best is None
            or score > best[0]
            or (
                score == best[0]
                and (
                    best_delta is None
                    or delta_minutes < best_delta
                )
            )
        ):
            best = (
                score,
                event,
                same_location,
                delta_minutes,
            )
            best_delta = delta_minutes

    return best


def evaluate_live_risk(
    db: Session,
    registration_number: str,
    anpr_event_id: str | None = None,
):
    registration_number = normalize(
        registration_number
    )

    vehicle = (
        db.query(Vehicle)
        .filter(
            Vehicle.registration_number
            == registration_number
        )
        .first()
    )

    if vehicle is None:
        return {
            "registration_number": registration_number,
            "registry_match": False,
            "risk_score": 20,
            "risk_tier": "LOW",
            "status": "VERIFY",
            "reasons": [
                "Vehicle not found in registry"
            ],
            "evidence": [],
            "movement": None,
            "fastag": None,
        }

    if anpr_event_id:
        latest_anpr = (
            db.query(ANPREvent)
            .filter(
                ANPREvent.event_id
                == anpr_event_id
            )
            .first()
        )
    else:
        latest_anpr = (
            db.query(ANPREvent)
            .filter(
                ANPREvent.registration_number
                == registration_number
            )
            .order_by(
                ANPREvent.timestamp.desc()
            )
            .first()
        )

    if latest_anpr is None:
        return {
            "registration_number": registration_number,
            "registry_match": True,
            "risk_score": 0,
            "risk_tier": "LOW",
            "status": "NO_ACTIVE_ANPR",
            "reasons": [],
            "evidence": [],
            "movement": None,
            "fastag": None,
        }

    score = 0
    reasons = []
    evidence = []

    # -----------------------------------------------------
    # REGISTRY STATUS
    # -----------------------------------------------------

    if normalize(vehicle.registry_status) == "SUSPENDED":
        score += 15
        reasons.append(
            "Registry status: SUSPENDED"
        )

    # -----------------------------------------------------
    # PERMIT
    # -----------------------------------------------------

    if normalize(vehicle.permit_status) == "EXPIRED":
        score += 10
        reasons.append(
            "Commercial permit expired"
        )

    # -----------------------------------------------------
    # FITNESS
    # -----------------------------------------------------

    if normalize(vehicle.fitness_status) == "EXPIRED":
        score += 10
        reasons.append(
            "Fitness certificate expired"
        )

    # -----------------------------------------------------
    # FASTAG STATUS
    # -----------------------------------------------------

    if normalize(vehicle.fastag_status) != "ACTIVE":
        score += 10
        reasons.append(
            f"FASTag status: {vehicle.fastag_status}"
        )

    # -----------------------------------------------------
    # VEHICLE TYPE
    # -----------------------------------------------------

    registered_type = normalize(
        vehicle.vehicle_type
    )

    detected_type = normalize(
        latest_anpr.detected_vehicle_type
    )

    if (
        registered_type
        and detected_type
        and registered_type != detected_type
    ):
        score += 30

        reasons.append(
            "Vehicle type mismatch: "
            f"registered {vehicle.vehicle_type}, "
            f"detected {latest_anpr.detected_vehicle_type}"
        )

        evidence.append(
            f"ANPR {latest_anpr.event_id}: "
            "vehicle type mismatch"
        )

    # -----------------------------------------------------
    # COLOUR
    # -----------------------------------------------------

    registered_colour = normalize(
        vehicle.registered_colour
    )

    detected_colour = normalize(
        latest_anpr.detected_colour
    )

    if (
        registered_colour
        and detected_colour
        and registered_colour != detected_colour
    ):
        score += 20

        reasons.append(
            "Colour mismatch: "
            f"registered {vehicle.registered_colour}, "
            f"detected {latest_anpr.detected_colour}"
        )

        evidence.append(
            f"ANPR {latest_anpr.event_id}: "
            "colour mismatch"
        )

    # -----------------------------------------------------
    # MOVEMENT
    # -----------------------------------------------------

    movement = analyze_latest_movement(
        db,
        registration_number,
        latest_anpr,
    )

    if (
        movement
        and movement["status"]
        == "MOVEMENT ANOMALY — REQUIRES VERIFICATION"
    ):
        score += 35

        reasons.append(
            movement["reason"]
        )

        evidence.append(
            "Movement analysis"
        )

    # -----------------------------------------------------
    # FASTAG CORRELATION
    # -----------------------------------------------------

    best_fastag = find_best_fastag_match(
        db,
        vehicle,
        latest_anpr,
    )

    fastag_result = None

    if best_fastag is not None:

        (
            match_score,
            fastag_event,
            same_location,
            time_difference,
        ) = best_fastag

        fastag_result = {
            "transaction_id": (
                fastag_event.transaction_id
            ),
            "fastag_id": fastag_event.fastag_id,
            "toll_plaza": fastag_event.toll_plaza,
            "timestamp": (
                fastag_event.timestamp.isoformat()
                if fastag_event.timestamp
                else None
            ),
            "transaction_status": (
                fastag_event.transaction_status
            ),
            "same_location": same_location,
            "time_difference_minutes": round(
                time_difference,
                2,
            ),
            "matched_signal_count": match_score,
        }

        if (
            fastag_event.fastag_id
            and vehicle.fastag_id
            and fastag_event.fastag_id
            != vehicle.fastag_id
        ):
            score += 30

            reasons.append(
                "FASTag identity mismatch: "
                f"registered {vehicle.fastag_id}, "
                f"observed {fastag_event.fastag_id}"
            )

            evidence.append(
                f"FASTag {fastag_event.transaction_id}"
            )

        if normalize(
            fastag_event.event_type
        ) == "TAG_IDENTITY_MISMATCH":
            score += 10

            reasons.append(
                "FASTag transaction identity mismatch"
            )

            evidence.append(
                f"FASTag {fastag_event.transaction_id}"
            )

    # -----------------------------------------------------
    # FINAL RESULT
    # -----------------------------------------------------

    score = min(
        100,
        score,
    )

    if score >= 80:
        tier = "CRITICAL"
    elif score >= 60:
        tier = "HIGH"
    elif score >= 30:
        tier = "MEDIUM"
    elif score > 0:
        tier = "LOW"
    else:
        tier = "LOW"

    status = (
        "VERIFY"
        if score > 0
        else "NORMAL"
    )

    return {
        "registration_number": registration_number,
        "registry_match": True,
        "latest_anpr_event": {
            "event_id": latest_anpr.event_id,
            "location": latest_anpr.location,
            "timestamp": (
                latest_anpr.timestamp.isoformat()
                if latest_anpr.timestamp
                else None
            ),
            "ocr_confidence": (
                latest_anpr.ocr_confidence
            ),
        },
        "vehicle": {
            "vehicle_id": vehicle.vehicle_id,
            "vehicle_type": vehicle.vehicle_type,
            "registered_colour": (
                vehicle.registered_colour
            ),
            "operator": vehicle.operator,
            "permit_status": vehicle.permit_status,
            "fitness_status": vehicle.fitness_status,
            "fastag_id": vehicle.fastag_id,
            "fastag_status": vehicle.fastag_status,
        },
        "risk_score": score,
        "risk_tier": tier,
        "status": status,
        "reasons": reasons,
        "evidence": evidence,
        "movement": movement,
        "fastag": fastag_result,
    }