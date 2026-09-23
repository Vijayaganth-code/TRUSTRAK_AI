from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Vehicle


router = APIRouter(
    prefix="/api/vehicles",
    tags=["Vehicles"],
)


@router.get("/{registration_number}")
def get_vehicle(
    registration_number: str,
    db: Session = Depends(get_db),
):
    plate = registration_number.strip().upper()

    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.registration_number == plate)
        .first()
    )

    if vehicle is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "Vehicle not found",
                "registration_number": plate,
            },
        )

    return {
        "vehicle_id": vehicle.vehicle_id,
        "registration_number": vehicle.registration_number,
        "state_code": vehicle.state_code,
        "vehicle_type": vehicle.vehicle_type,
        "commercial_vehicle": vehicle.commercial_vehicle,
        "manufacturer": vehicle.manufacturer,
        "model": vehicle.model,
        "registered_colour": vehicle.registered_colour,
        "operator": vehicle.operator,
        "permit_status": vehicle.permit_status,
        "permit_expiry": vehicle.permit_expiry,
        "fitness_status": vehicle.fitness_status,
        "fitness_expiry": vehicle.fitness_expiry,
        "insurance_status": vehicle.insurance_status,
        "insurance_expiry": vehicle.insurance_expiry,
        "puc_status": vehicle.puc_status,
        "puc_expiry": vehicle.puc_expiry,
        "fastag_id": vehicle.fastag_id,
        "fastag_status": vehicle.fastag_status,
        "registry_status": vehicle.registry_status,
        "data_source": vehicle.data_source,
    }
