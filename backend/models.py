from datetime import datetime
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
)

from .database import Base


# =========================================================
# VEHICLE REGISTRY
# =========================================================

class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, autoincrement=True)

    vehicle_id = Column(String(30), unique=True, index=True, nullable=False)
    registration_number = Column(String(20), unique=True, index=True, nullable=False)

    state_code = Column(String(10))
    vehicle_type = Column(String(50))
    commercial_vehicle = Column(String(10))

    manufacturer = Column(String(80))
    model = Column(String(80))
    registered_colour = Column(String(40))
    operator = Column(String(120))

    permit_status = Column(String(30))
    permit_expiry = Column(Date)

    fitness_status = Column(String(30))
    fitness_expiry = Column(Date)

    insurance_status = Column(String(30))
    insurance_expiry = Column(Date)

    puc_status = Column(String(30))
    puc_expiry = Column(Date)

    fastag_id = Column(String(50), index=True)
    fastag_status = Column(String(30))

    registry_status = Column(String(30))

    chassis_reference = Column(String(80))
    engine_reference = Column(String(80))

    source_image_id = Column(String(100))
    source_image_path = Column(String(300))

    data_source = Column(String(50))


# =========================================================
# ANPR EVENTS
# =========================================================

class ANPREvent(Base):
    __tablename__ = "anpr_events"

    id = Column(Integer, primary_key=True, autoincrement=True)

    event_id = Column(String(40), unique=True, index=True, nullable=False)

    registration_number = Column(
        String(20),
        index=True,
        nullable=False,
    )

    camera_id = Column(String(40), index=True)
    location = Column(String(80), index=True)

    timestamp = Column(DateTime, index=True)

    detected_vehicle_type = Column(String(50))
    detected_colour = Column(String(40))

    ocr_confidence = Column(Float)

    event_type = Column(String(40))


# =========================================================
# FASTAG EVENTS
# =========================================================

class FASTagEvent(Base):
    __tablename__ = "fastag_events"

    id = Column(Integer, primary_key=True, autoincrement=True)

    transaction_id = Column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )

    registration_number = Column(
        String(20),
        index=True,
        nullable=False,
    )

    fastag_id = Column(String(50), index=True)

    toll_plaza = Column(String(120))
    timestamp = Column(DateTime, index=True)

    transaction_status = Column(String(40))

    amount = Column(Float)

    event_type = Column(String(40))


# =========================================================
# MOVEMENT EVENTS
# =========================================================

class MovementEvent(Base):
    __tablename__ = "movement_events"

    id = Column(Integer, primary_key=True, autoincrement=True)

    movement_id = Column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )

    registration_number = Column(
        String(20),
        index=True,
        nullable=False,
    )

    from_location = Column(String(80))
    to_location = Column(String(80))

    departure_time = Column(DateTime, index=True)
    arrival_time = Column(DateTime, index=True)

    movement_status = Column(String(40))
    scenario = Column(String(40))


# =========================================================
# VERIFICATION CASES
# =========================================================

class VerificationCase(Base):
    __tablename__ = "verification_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)

    case_id = Column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )

    rank = Column(Integer)

    registration_number = Column(
        String(20),
        index=True,
        nullable=False,
    )

    risk_score = Column(Integer)
    risk_tier = Column(String(30))
    status = Column(String(30))

    reasons = Column(Text)
    evidence = Column(Text)


# =========================================================
# AUDIT LOGS
# =========================================================

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    timestamp = Column(
        DateTime,
        index=True,
        nullable=False,
    )

    action = Column(
        String(50),
        index=True,
        nullable=False,
    )

    case_id = Column(
        String(50),
        index=True,
    )

    registration_number = Column(
        String(20),
        index=True,
    )

    previous_status = Column(
        String(30),
    )

    new_status = Column(
        String(30),
    )

    details = Column(Text)