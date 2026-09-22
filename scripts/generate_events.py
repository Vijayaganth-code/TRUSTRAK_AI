import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

REGISTRY_FILE = PROJECT_ROOT / "data" / "vehicle_registry.csv"

ANPR_FILE = PROJECT_ROOT / "data" / "anpr_events.csv"
FASTAG_FILE = PROJECT_ROOT / "data" / "fastag_events.csv"
MOVEMENT_FILE = PROJECT_ROOT / "data" / "movement_events.csv"

random.seed(20260922)

LOCATIONS = {
    "Chennai": {
        "lat": 13.0827,
        "lon": 80.2707,
    },
    "Vellore": {
        "lat": 12.9165,
        "lon": 79.1325,
    },
    "Salem": {
        "lat": 11.6643,
        "lon": 78.1460,
    },
    "Coimbatore": {
        "lat": 11.0168,
        "lon": 76.9558,
    },
    "Trichy": {
        "lat": 10.7905,
        "lon": 78.7047,
    },
    "Madurai": {
        "lat": 9.9252,
        "lon": 78.1198,
    },
    "Thanjavur": {
        "lat": 10.7870,
        "lon": 79.1378,
    },
    "Tirunelveli": {
        "lat": 8.7139,
        "lon": 77.7567,
    },
}

TOLL_PLAZAS = {
    "Chennai": "Chennai Toll Plaza",
    "Vellore": "Vellore Toll Plaza",
    "Salem": "Salem Toll Plaza",
    "Coimbatore": "Coimbatore Toll Plaza",
    "Trichy": "Trichy Toll Plaza",
    "Madurai": "Madurai Toll Plaza",
    "Thanjavur": "Thanjavur Toll Plaza",
    "Tirunelveli": "Tirunelveli Toll Plaza",
}

REFERENCE_TIME = datetime(2026, 9, 22, 8, 0, 0)


def read_registry():
    with REGISTRY_FILE.open(
        "r",
        encoding="utf-8",
        newline=""
    ) as file:
        return list(csv.DictReader(file))


def choose_location():
    return random.choice(list(LOCATIONS.keys()))


def choose_camera(location):
    return f"CAM-{location[:3].upper()}-{random.randint(1, 4):02d}"


def make_timestamp(offset_minutes):
    return REFERENCE_TIME + timedelta(minutes=offset_minutes)


def main():
    registry = read_registry()

    if not registry:
        raise RuntimeError("Vehicle registry is empty.")

    print("=" * 60)
    print("TRUSTRAK AI - SYNTHETIC EVENT GENERATOR")
    print("=" * 60)

    anpr_rows = []
    fastag_rows = []
    movement_rows = []

    event_counter = 1
    fastag_counter = 1

    # ---------------------------------------------------------
    # 1. NORMAL TRAFFIC EVENTS
    # ---------------------------------------------------------
    for vehicle in registry:
        plate = vehicle["registration_number"]

        location = choose_location()

        ts = make_timestamp(
            random.randint(0, 12 * 60)
        )

        anpr_rows.append(
            {
                "event_id": f"ANPR-{event_counter:06d}",
                "registration_number": plate,
                "camera_id": choose_camera(location),
                "location": location,
                "timestamp": ts.isoformat(),
                "detected_vehicle_type": vehicle["vehicle_type"],
                "detected_colour": vehicle["registered_colour"],
                "ocr_confidence": round(
                    random.uniform(0.88, 0.99),
                    3
                ),
                "event_type": "NORMAL",
            }
        )

        event_counter += 1

        fastag_status = (
            "SUCCESS"
            if vehicle["fastag_status"] == "ACTIVE"
            else "EXCEPTION"
        )

        fastag_rows.append(
            {
                "transaction_id": f"FT-TXN-{fastag_counter:06d}",
                "registration_number": plate,
                "fastag_id": vehicle["fastag_id"],
                "toll_plaza": TOLL_PLAZAS[location],
                "timestamp": ts.isoformat(),
                "transaction_status": fastag_status,
                "amount": round(
                    random.uniform(45, 220),
                    2
                ),
                "event_type": "NORMAL",
            }
        )

        fastag_counter += 1

        movement_rows.append(
            {
                "movement_id": f"MOV-{len(movement_rows) + 1:06d}",
                "registration_number": plate,
                "from_location": "ENTRY",
                "to_location": location,
                "departure_time": (
                    ts - timedelta(minutes=30)
                ).isoformat(),
                "arrival_time": ts.isoformat(),
                "movement_status": "NORMAL",
                "scenario": "NORMAL",
            }
        )

    # ---------------------------------------------------------
    # 2. NORMAL RETURN TRIP
    # Same vehicle returning to previous location is NOT fraud.
    # ---------------------------------------------------------
    for index, vehicle in enumerate(registry[:40]):
        plate = vehicle["registration_number"]

        ts1 = make_timestamp(600 + index * 3)
        ts2 = ts1 + timedelta(hours=2, minutes=30)

        anpr_rows.append(
            {
                "event_id": f"ANPR-{event_counter:06d}",
                "registration_number": plate,
                "camera_id": "CAM-CHN-01",
                "location": "Chennai",
                "timestamp": ts1.isoformat(),
                "detected_vehicle_type": vehicle["vehicle_type"],
                "detected_colour": vehicle["registered_colour"],
                "ocr_confidence": 0.97,
                "event_type": "NORMAL_RETURN_TRIP",
            }
        )
        event_counter += 1

        anpr_rows.append(
            {
                "event_id": f"ANPR-{event_counter:06d}",
                "registration_number": plate,
                "camera_id": "CAM-CHN-02",
                "location": "Chennai",
                "timestamp": ts2.isoformat(),
                "detected_vehicle_type": vehicle["vehicle_type"],
                "detected_colour": vehicle["registered_colour"],
                "ocr_confidence": 0.96,
                "event_type": "NORMAL_RETURN_TRIP",
            }
        )
        event_counter += 1

    # ---------------------------------------------------------
    # 3. VEHICLE TYPE MISMATCH
    # Same plate reported on a different vehicle class.
    # ---------------------------------------------------------
    for index, vehicle in enumerate(registry[40:60]):
        plate = vehicle["registration_number"]

        fake_type = (
            "Bike"
            if vehicle["vehicle_type"] != "Bike"
            else "Truck"
        )

        location = "Coimbatore"
        ts = make_timestamp(
            900 + index * 4
        )

        anpr_rows.append(
            {
                "event_id": f"ANPR-{event_counter:06d}",
                "registration_number": plate,
                "camera_id": "CAM-CBE-03",
                "location": location,
                "timestamp": ts.isoformat(),
                "detected_vehicle_type": fake_type,
                "detected_colour": vehicle["registered_colour"],
                "ocr_confidence": 0.95,
                "event_type": "VEHICLE_TYPE_MISMATCH",
            }
        )
        event_counter += 1

    # ---------------------------------------------------------
    # 4. COLOUR MISMATCH
    # ---------------------------------------------------------
    for index, vehicle in enumerate(registry[60:80]):
        plate = vehicle["registration_number"]

        alternate_colour = (
            "Red"
            if vehicle["registered_colour"] != "Red"
            else "Blue"
        )

        ts = make_timestamp(
            1000 + index * 4
        )

        anpr_rows.append(
            {
                "event_id": f"ANPR-{event_counter:06d}",
                "registration_number": plate,
                "camera_id": "CAM-SLM-02",
                "location": "Salem",
                "timestamp": ts.isoformat(),
                "detected_vehicle_type": vehicle["vehicle_type"],
                "detected_colour": alternate_colour,
                "ocr_confidence": 0.94,
                "event_type": "COLOUR_MISMATCH",
            }
        )
        event_counter += 1

    # ---------------------------------------------------------
    # 5. FASTAG MISMATCH
    # Correct plate + different FASTag.
    # ---------------------------------------------------------
    for index, vehicle in enumerate(registry[80:100]):
        plate = vehicle["registration_number"]

        fake_fastag = f"FT-FAKE-{index + 1:04d}"

        ts = make_timestamp(
            1100 + index * 4
        )

        fastag_rows.append(
            {
                "transaction_id": f"FT-TXN-{fastag_counter:06d}",
                "registration_number": plate,
                "fastag_id": fake_fastag,
                "toll_plaza": "Vellore Toll Plaza",
                "timestamp": ts.isoformat(),
                "transaction_status": "TAG_IDENTITY_MISMATCH",
                "amount": 120.00,
                "event_type": "FASTAG_MISMATCH",
            }
        )

        fastag_counter += 1

    # ---------------------------------------------------------
    # 6. IMPOSSIBLE TRAVEL
    # Same plate seen far away in an unrealistically short time.
    # ---------------------------------------------------------
    for index, vehicle in enumerate(registry[100:120]):
        plate = vehicle["registration_number"]

        ts1 = make_timestamp(
            1200 + index * 5
        )

        ts2 = ts1 + timedelta(minutes=20)

        anpr_rows.append(
            {
                "event_id": f"ANPR-{event_counter:06d}",
                "registration_number": plate,
                "camera_id": "CAM-CHN-01",
                "location": "Chennai",
                "timestamp": ts1.isoformat(),
                "detected_vehicle_type": vehicle["vehicle_type"],
                "detected_colour": vehicle["registered_colour"],
                "ocr_confidence": 0.98,
                "event_type": "IMPOSSIBLE_TRAVEL",
            }
        )
        event_counter += 1

        anpr_rows.append(
            {
                "event_id": f"ANPR-{event_counter:06d}",
                "registration_number": plate,
                "camera_id": "CAM-CBE-01",
                "location": "Coimbatore",
                "timestamp": ts2.isoformat(),
                "detected_vehicle_type": vehicle["vehicle_type"],
                "detected_colour": vehicle["registered_colour"],
                "ocr_confidence": 0.97,
                "event_type": "IMPOSSIBLE_TRAVEL",
            }
        )
        event_counter += 1

        movement_rows.append(
            {
                "movement_id": f"MOV-{len(movement_rows) + 1:06d}",
                "registration_number": plate,
                "from_location": "Chennai",
                "to_location": "Coimbatore",
                "departure_time": ts1.isoformat(),
                "arrival_time": ts2.isoformat(),
                "movement_status": "IMPOSSIBLE_SPEED_SIGNAL",
                "scenario": "IMPOSSIBLE_TRAVEL",
            }
        )

    # ---------------------------------------------------------
    # 7. EXPIRED PERMIT
    # ---------------------------------------------------------
    expired_vehicles = [
        v for v in registry
        if v["permit_status"] == "EXPIRED"
    ]

    for index, vehicle in enumerate(expired_vehicles[:40]):
        plate = vehicle["registration_number"]

        location = "Chennai"
        ts = make_timestamp(
            1400 + index * 3
        )

        anpr_rows.append(
            {
                "event_id": f"ANPR-{event_counter:06d}",
                "registration_number": plate,
                "camera_id": "CAM-CHN-04",
                "location": location,
                "timestamp": ts.isoformat(),
                "detected_vehicle_type": vehicle["vehicle_type"],
                "detected_colour": vehicle["registered_colour"],
                "ocr_confidence": 0.96,
                "event_type": "EXPIRED_PERMIT",
            }
        )

        event_counter += 1

    # ---------------------------------------------------------
    # 8. UNKNOWN PLATES
    # These deliberately do not exist in vehicle_registry.csv.
    # ---------------------------------------------------------
    unknown_plates = [
        "TN99ZZ9999",
        "TN88XX8888",
        "KA99FA1234",
        "MH99ZZ5555",
        "AP99YY7777",
    ]

    for index, plate in enumerate(unknown_plates):
        ts = make_timestamp(
            1500 + index * 5
        )

        anpr_rows.append(
            {
                "event_id": f"ANPR-{event_counter:06d}",
                "registration_number": plate,
                "camera_id": "CAM-CBE-04",
                "location": "Coimbatore",
                "timestamp": ts.isoformat(),
                "detected_vehicle_type": "Unknown",
                "detected_colour": "Unknown",
                "ocr_confidence": 0.91,
                "event_type": "UNKNOWN_PLATE",
            }
        )

        event_counter += 1

    # ---------------------------------------------------------
    # WRITE ANPR CSV
    # ---------------------------------------------------------
    anpr_fields = [
        "event_id",
        "registration_number",
        "camera_id",
        "location",
        "timestamp",
        "detected_vehicle_type",
        "detected_colour",
        "ocr_confidence",
        "event_type",
    ]

    with ANPR_FILE.open(
        "w",
        encoding="utf-8",
        newline=""
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=anpr_fields
        )
        writer.writeheader()
        writer.writerows(anpr_rows)

    # ---------------------------------------------------------
    # WRITE FASTAG CSV
    # ---------------------------------------------------------
    fastag_fields = [
        "transaction_id",
        "registration_number",
        "fastag_id",
        "toll_plaza",
        "timestamp",
        "transaction_status",
        "amount",
        "event_type",
    ]

    with FASTAG_FILE.open(
        "w",
        encoding="utf-8",
        newline=""
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fastag_fields
        )
        writer.writeheader()
        writer.writerows(fastag_rows)

    # ---------------------------------------------------------
    # WRITE MOVEMENT CSV
    # ---------------------------------------------------------
    movement_fields = [
        "movement_id",
        "registration_number",
        "from_location",
        "to_location",
        "departure_time",
        "arrival_time",
        "movement_status",
        "scenario",
    ]

    with MOVEMENT_FILE.open(
        "w",
        encoding="utf-8",
        newline=""
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=movement_fields
        )
        writer.writeheader()
        writer.writerows(movement_rows)

    print()
    print(f"Vehicles in registry : {len(registry)}")
    print(f"ANPR events           : {len(anpr_rows)}")
    print(f"FASTag events         : {len(fastag_rows)}")
    print(f"Movement events       : {len(movement_rows)}")

    print()
    print("Created:")
    print(f"  {ANPR_FILE}")
    print(f"  {FASTAG_FILE}")
    print(f"  {MOVEMENT_FILE}")

    print()
    print("Synthetic event generation complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
