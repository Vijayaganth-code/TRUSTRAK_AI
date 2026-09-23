from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import FASTagEvent, Vehicle


router = APIRouter(
    prefix="/api/fastag",
    tags=["FASTag"],
)


# =========================================================
# REQUEST MODEL
# =========================================================

class FASTagEventCreate(BaseModel):
    registration_number: str = Field(min_length=1)
    fastag_id: str = Field(min_length=1)
    toll_plaza: str = Field(min_length=1)

    timestamp: Optional[datetime] = None

    transaction_status: str = "SUCCESS"
    amount: float = 0.0
    event_type: str = "NORMAL"


# =========================================================
# CREATE FASTAG EVENT
# =========================================================

@router.post("/events")
def create_fastag_event(
    event_data: FASTagEventCreate,
    db: Session = Depends(get_db),
):
    plate = event_data.registration_number.strip().upper()
    fastag_id = event_data.fastag_id.strip().upper()

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
    # Generate transaction ID
    # -----------------------------------------------------

    last_transaction = (
        db.query(FASTagEvent)
        .order_by(FASTagEvent.id.desc())
        .first()
    )

    if last_transaction is None:
        next_number = 1
    else:
        try:
            next_number = (
                int(
                    last_transaction.transaction_id
                    .split("-")[-1]
                )
                + 1
            )
        except (ValueError, AttributeError):
            next_number = last_transaction.id + 1

    transaction_id = f"FT-TXN-{next_number:06d}"

    # -----------------------------------------------------
    # Timestamp
    # -----------------------------------------------------

    event_timestamp = (
        event_data.timestamp
        if event_data.timestamp
        else datetime.now()
    )

    # -----------------------------------------------------
    # Event type
    # -----------------------------------------------------

    event_type = event_data.event_type.strip().upper()

    if vehicle is None:
        event_type = "UNKNOWN_REGISTRY"

    # -----------------------------------------------------
    # Create event
    # -----------------------------------------------------

    event = FASTagEvent(
        transaction_id=transaction_id,
        registration_number=plate,
        fastag_id=fastag_id,
        toll_plaza=event_data.toll_plaza.strip(),
        timestamp=event_timestamp,
        transaction_status=(
            event_data.transaction_status.strip().upper()
        ),
        amount=event_data.amount,
        event_type=event_type,
    )

    db.add(event)

    try:
        db.commit()
        db.refresh(event)

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Unable to save FASTag event: {exc}",
        )

    return {
        "success": True,
        "transaction": {
            "transaction_id": event.transaction_id,
            "registration_number": event.registration_number,
            "fastag_id": event.fastag_id,
            "toll_plaza": event.toll_plaza,
            "timestamp": event.timestamp,
            "transaction_status": event.transaction_status,
            "amount": event.amount,
            "event_type": event.event_type,
        },
        "registry_match": vehicle is not None,
        "vehicle": (
            {
                "vehicle_id": vehicle.vehicle_id,
                "registration_number": (
                    vehicle.registration_number
                ),
                "fastag_id": vehicle.fastag_id,
                "fastag_status": vehicle.fastag_status,
                "vehicle_type": vehicle.vehicle_type,
                "operator": vehicle.operator,
            }
            if vehicle
            else None
        ),
    }


# =========================================================
# GET FASTAG HISTORY
# =========================================================

@router.get("/{registration_number}")
def get_fastag_history(
    registration_number: str,
    db: Session = Depends(get_db),
):
    plate = registration_number.strip().upper()

    events = (
        db.query(FASTagEvent)
        .filter(
            FASTagEvent.registration_number == plate
        )
        .order_by(FASTagEvent.timestamp.desc())
        .all()
    )

    if not events:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "No FASTag events found",
                "registration_number": plate,
            },
        )

    return {
        "registration_number": plate,
        "event_count": len(events),
        "events": [
            {
                "transaction_id": event.transaction_id,
                "fastag_id": event.fastag_id,
                "toll_plaza": event.toll_plaza,
                "timestamp": event.timestamp,
                "transaction_status": (
                    event.transaction_status
                ),
                "amount": event.amount,
                "event_type": event.event_type,
            }
            for event in events
        ],
    }


# =========================================================
# GET LATEST FASTAG EVENT
# =========================================================

@router.get("/{registration_number}/latest")
def get_latest_fastag_event(
    registration_number: str,
    db: Session = Depends(get_db),
):
    plate = registration_number.strip().upper()

    event = (
        db.query(FASTagEvent)
        .filter(
            FASTagEvent.registration_number == plate
        )
        .order_by(FASTagEvent.timestamp.desc())
        .first()
    )

    if event is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "No FASTag event found",
                "registration_number": plate,
            },
        )

    return {
        "transaction_id": event.transaction_id,
        "registration_number": event.registration_number,
        "fastag_id": event.fastag_id,
        "toll_plaza": event.toll_plaza,
        "timestamp": event.timestamp,
        "transaction_status": event.transaction_status,
        "amount": event.amount,
        "event_type": event.event_type,
    }