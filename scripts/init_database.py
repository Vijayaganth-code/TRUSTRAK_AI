import csv
from datetime import datetime
from pathlib import Path

from backend.database import Base, SessionLocal, engine
from backend.models import (
    ANPREvent,
    FASTagEvent,
    MovementEvent,
    Vehicle,
    VerificationCase,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"


# =========================================================
# HELPERS
# =========================================================

def read_csv(filename):
    path = DATA_DIR / filename

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        return list(csv.DictReader(file))


def parse_date(value):
    if not value:
        return None

    return datetime.strptime(
        value,
        "%Y-%m-%d",
    ).date()


def parse_datetime(value):
    if not value:
        return None

    return datetime.fromisoformat(value)


def to_float(value):
    if value in (None, ""):
        return None

    return float(value)


def to_int(value):
    if value in (None, ""):
        return None

    return int(value)


# =========================================================
# CREATE TABLES
# =========================================================

def create_tables():
    Base.metadata.create_all(engine)


# =========================================================
# IMPORT VEHICLES
# =========================================================

def import_vehicles(session):

    rows = read_csv("vehicle_registry.csv")

    for row in rows:

        vehicle = Vehicle(
            vehicle_id=row["vehicle_id"],
            registration_number=row["registration_number"],
            state_code=row["state_code"],
            vehicle_type=row["vehicle_type"],
            commercial_vehicle=row["commercial_vehicle"],
            manufacturer=row["manufacturer"],
            model=row["model"],
            registered_colour=row["registered_colour"],
            operator=row["operator"],
            permit_status=row["permit_status"],
            permit_expiry=parse_date(row["permit_expiry"]),
            fitness_status=row["fitness_status"],
            fitness_expiry=parse_date(row["fitness_expiry"]),
            insurance_status=row["insurance_status"],
            insurance_expiry=parse_date(row["insurance_expiry"]),
            puc_status=row["puc_status"],
            puc_expiry=parse_date(row["puc_expiry"]),
            fastag_id=row["fastag_id"],
            fastag_status=row["fastag_status"],
            registry_status=row["registry_status"],
            chassis_reference=row["chassis_reference"],
            engine_reference=row["engine_reference"],
            source_image_id=row["source_image_id"],
            source_image_path=row["source_image_path"],
            data_source=row["data_source"],
        )

        session.add(vehicle)

    print(f"Vehicles imported: {len(rows)}")


# =========================================================
# IMPORT ANPR
# =========================================================

def import_anpr_events(session):

    rows = read_csv("anpr_events.csv")

    for row in rows:

        event = ANPREvent(
            event_id=row["event_id"],
            registration_number=row["registration_number"],
            camera_id=row["camera_id"],
            location=row["location"],
            timestamp=parse_datetime(row["timestamp"]),
            detected_vehicle_type=row["detected_vehicle_type"],
            detected_colour=row["detected_colour"],
            ocr_confidence=to_float(row["ocr_confidence"]),
            event_type=row["event_type"],
        )

        session.add(event)

    print(f"ANPR events imported: {len(rows)}")


# =========================================================
# IMPORT FASTAG
# =========================================================

def import_fastag_events(session):

    rows = read_csv("fastag_events.csv")

    for row in rows:

        event = FASTagEvent(
            transaction_id=row["transaction_id"],
            registration_number=row["registration_number"],
            fastag_id=row["fastag_id"],
            toll_plaza=row["toll_plaza"],
            timestamp=parse_datetime(row["timestamp"]),
            transaction_status=row["transaction_status"],
            amount=to_float(row["amount"]),
            event_type=row["event_type"],
        )

        session.add(event)

    print(f"FASTag events imported: {len(rows)}")


# =========================================================
# IMPORT MOVEMENT
# =========================================================

def import_movement_events(session):

    rows = read_csv("movement_events.csv")

    for row in rows:

        event = MovementEvent(
            movement_id=row["movement_id"],
            registration_number=row["registration_number"],
            from_location=row["from_location"],
            to_location=row["to_location"],
            departure_time=parse_datetime(row["departure_time"]),
            arrival_time=parse_datetime(row["arrival_time"]),
            movement_status=row["movement_status"],
            scenario=row["scenario"],
        )

        session.add(event)

    print(f"Movement events imported: {len(rows)}")


# =========================================================
# IMPORT VERIFICATION CASES
# =========================================================

def import_verification_cases(session):

    rows = read_csv("verification_cases.csv")

    for row in rows:

        case = VerificationCase(
            case_id=row["case_id"],
            rank=to_int(row["rank"]),
            registration_number=row["registration_number"],
            risk_score=to_int(row["risk_score"]),
            risk_tier=row["risk_tier"],
            status=row["status"],
            reasons=row["reasons"],
            evidence=row["evidence"],
        )

        session.add(case)

    print(f"Verification cases imported: {len(rows)}")


# =========================================================
# MAIN
# =========================================================

def main():

    print("=" * 70)
    print("TRUSTRAK AI DATABASE INITIALIZATION")
    print("=" * 70)

    create_tables()

    session = SessionLocal()

    try:

        import_vehicles(session)
        import_anpr_events(session)
        import_fastag_events(session)
        import_movement_events(session)
        import_verification_cases(session)

        session.commit()

        print()
        print("Database initialization completed successfully.")
        print(f"Database location: {PROJECT_ROOT / 'database' / 'trustrak.db'}")

    except Exception as exc:

        session.rollback()

        print()
        print("ERROR:", exc)

        raise

    finally:
        session.close()


if __name__ == "__main__":
    main()
