import csv
import random
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = PROJECT_ROOT / "data" / "plate_dataset.csv"
OUTPUT_FILE = PROJECT_ROOT / "data" / "vehicle_registry.csv"

random.seed(20260922)

TODAY = date.today()

COLOURS = [
    "White",
    "Black",
    "Silver",
    "Blue",
    "Red",
    "Grey",
    "Yellow",
]

OPERATORS = [
    "Apex Logistics",
    "Southern Freight",
    "Metro Transit",
    "Kaveri Transport",
    "Chennai Cargo",
    "Tamil Fleet Services",
    "National Route Logistics",
    "Coastal Commercials",
    "GreenLine Transport",
    "Sri Lakshmi Logistics",
]

VEHICLE_CONFIG = {
    "Truck": [
        ("Tata", "Prima"),
        ("Ashok Leyland", "AVTR"),
        ("BharatBenz", "3123R"),
    ],
    "Mini Truck": [
        ("Tata", "407"),
        ("Mahindra", "Bolero Pickup"),
        ("Ashok Leyland", "Dost"),
    ],
    "Bus": [
        ("Ashok Leyland", "Viking"),
        ("Tata", "Starbus"),
        ("Volvo", "9400"),
    ],
    "Car": [
        ("Maruti", "Ertiga"),
        ("Hyundai", "Aura"),
        ("Toyota", "Innova"),
    ],
    "Bike": [
        ("Honda", "Shine"),
        ("TVS", "Apache"),
        ("Bajaj", "Pulsar"),
    ],
}

VEHICLE_TYPES = [
    ("Truck", 35),
    ("Mini Truck", 20),
    ("Bus", 10),
    ("Car", 20),
    ("Bike", 15),
]


def choose_vehicle_type():
    types = [item[0] for item in VEHICLE_TYPES]
    weights = [item[1] for item in VEHICLE_TYPES]
    return random.choices(types, weights=weights, k=1)[0]


def choose_date(days_min, days_max):
    return TODAY + timedelta(
        days=random.randint(days_min, days_max)
    )


def status_from_expiry(expiry):
    return "VALID" if expiry >= TODAY else "EXPIRED"


def unique_rows():
    with INPUT_FILE.open(
        "r",
        encoding="utf-8",
        newline=""
    ) as file:
        reader = csv.DictReader(file)

        seen = set()

        for row in reader:
            if row["status"] != "OK":
                continue

            plate = row["license_number"].strip().upper()

            if not plate or plate in seen:
                continue

            seen.add(plate)

            yield {
                "plate": plate,
                "state_code": row["state_code"],
                "image_id": row["image_id"],
                "image_path": row["image_path"],
            }


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}"
        )

    records = list(unique_rows())

    print("=" * 60)
    print("TRUSTRAK AI - SYNTHETIC VEHICLE REGISTRY GENERATOR")
    print("=" * 60)

    output_rows = []

    for index, item in enumerate(records, start=1):

        vehicle_type = choose_vehicle_type()

        manufacturer, model = random.choice(
            VEHICLE_CONFIG[vehicle_type]
        )

        colour = random.choice(COLOURS)

        operator = random.choice(OPERATORS)

        if random.random() < 0.08:
            permit_expiry = choose_date(-300, -1)
        else:
            permit_expiry = choose_date(30, 900)

        if random.random() < 0.06:
            fitness_expiry = choose_date(-180, -1)
        else:
            fitness_expiry = choose_date(30, 730)

        if random.random() < 0.04:
            insurance_expiry = choose_date(-120, -1)
        else:
            insurance_expiry = choose_date(30, 365)

        if random.random() < 0.05:
            puc_expiry = choose_date(-90, -1)
        else:
            puc_expiry = choose_date(30, 365)
        permit_status = status_from_expiry(permit_expiry)
        fitness_status = status_from_expiry(fitness_expiry)
        insurance_status = status_from_expiry(insurance_expiry)
        puc_status = status_from_expiry(puc_expiry)

        fastag_id = f"FT-{index:06d}"

        fastag_status = (
            "ACTIVE"
            if random.random() > 0.07
            else random.choice(
                ["INACTIVE", "BLACKLISTED", "KYC_PENDING"]
            )
        )

        commercial_vehicle = (
            "YES"
            if vehicle_type in ["Truck", "Mini Truck", "Bus"]
            else "NO"
        )

        registry_status = (
            "ACTIVE"
            if random.random() > 0.02
            else "SUSPENDED"
        )

        chassis_reference = f"CHASSIS-SYN-{index:06d}"
        engine_reference = f"ENGINE-SYN-{index:06d}"

        output_rows.append(
            {
                "vehicle_id": f"VH-{index:06d}",
                "registration_number": item["plate"],
                "state_code": item["state_code"],
                "vehicle_type": vehicle_type,
                "commercial_vehicle": commercial_vehicle,
                "manufacturer": manufacturer,
                "model": model,
                "registered_colour": colour,
                "operator": operator,
                "permit_status": permit_status,
                "permit_expiry": permit_expiry.isoformat(),
                "fitness_status": fitness_status,
                "fitness_expiry": fitness_expiry.isoformat(),
                "insurance_status": insurance_status,
                "insurance_expiry": insurance_expiry.isoformat(),
                "puc_status": puc_status,
                "puc_expiry": puc_expiry.isoformat(),
                "fastag_id": fastag_id,
                "fastag_status": fastag_status,
                "registry_status": registry_status,
                "chassis_reference": chassis_reference,
                "engine_reference": engine_reference,
                "source_image_id": item["image_id"],
                "source_image_path": item["image_path"],
                "data_source": "SYNTHETIC_PROTOTYPE",
            }
        )

    fields = list(output_rows[0].keys())

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
        newline=""
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields
        )
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Input records used : {len(records)}")
    print(f"Registry records    : {len(output_rows)}")
    print(f"Output              : {OUTPUT_FILE}")

    print()
    print("VEHICLE TYPE SUMMARY")

    type_counts = {}

    for row in output_rows:
        vehicle_type = row["vehicle_type"]
        type_counts[vehicle_type] = (
            type_counts.get(vehicle_type, 0) + 1
        )

    for vehicle_type, count in sorted(type_counts.items()):
        print(f"  {vehicle_type:<15} {count}")

    print()
    print("REGULATORY STATUS SUMMARY")

    for field in [
        "permit_status",
        "fitness_status",
        "insurance_status",
        "puc_status",
        "fastag_status",
    ]:
        counts = {}

        for row in output_rows:
            value = row[field]
            counts[value] = counts.get(value, 0) + 1

        print(f"\n{field}:")
        for value, count in sorted(counts.items()):
            print(f"  {value:<15} {count}")

    print()
    print("Synthetic registry generation complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
