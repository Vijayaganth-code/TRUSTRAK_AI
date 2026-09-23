import csv
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATASET_DIR = (
    PROJECT_ROOT
    / "dataset"
    / "NumberPlate_Annotated_Dataset-main"
)

IMAGES_DIR = DATASET_DIR / "Images"
LABELS_DIR = DATASET_DIR / "Labels"
CSV_FILE = DATASET_DIR / "boundaries.csv"

OUTPUT_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"

OUTPUT_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)


def normalize_plate(value: str) -> str:
    """
    Normalize an Indian vehicle registration number for lookup.
    Example:
        'TN 63 BV 7954' -> 'TN63BV7954'
    """
    if value is None:
        return ""

    value = str(value).upper().strip()
    return re.sub(r"[^A-Z0-9]", "", value)


def get_xml_value(root, tag):
    node = root.find(f".//{tag}")
    return node.text.strip() if node is not None and node.text else ""


def parse_xml(xml_path: Path):
    """
    Read the license number and bounding box from Pascal VOC XML.
    """
    try:
        root = ET.parse(xml_path).getroot()
    except Exception as exc:
        return {
            "xml_valid": False,
            "xml_plate": "",
            "xmin": "",
            "ymin": "",
            "xmax": "",
            "ymax": "",
            "xml_error": str(exc),
        }

    obj = root.find(".//object")

    if obj is None:
        return {
            "xml_valid": True,
            "xml_plate": "",
            "xmin": "",
            "ymin": "",
            "xmax": "",
            "ymax": "",
            "xml_error": "No object element",
        }

    name = obj.find("name")
    bbox = obj.find("bndbox")

    xml_plate = ""
    if name is not None and name.text:
        xml_plate = normalize_plate(name.text)

    values = {
        "xmin": "",
        "ymin": "",
        "xmax": "",
        "ymax": "",
    }

    if bbox is not None:
        for key in values:
            node = bbox.find(key)
            if node is not None and node.text:
                values[key] = node.text.strip()

    return {
        "xml_valid": True,
        "xml_plate": xml_plate,
        **values,
        "xml_error": "",
    }


def main():
    if not CSV_FILE.exists():
        raise FileNotFoundError(f"CSV not found: {CSV_FILE}")

    if not IMAGES_DIR.exists():
        raise FileNotFoundError(f"Images folder not found: {IMAGES_DIR}")

    if not LABELS_DIR.exists():
        raise FileNotFoundError(f"Labels folder not found: {LABELS_DIR}")

    print("=" * 60)
    print("TRUSTRAK AI - DATASET IMPORTER")
    print("=" * 60)

    image_files = {
        p.stem.upper(): p
        for p in IMAGES_DIR.iterdir()
        if p.is_file()
    }

    xml_files = {
        p.stem.upper(): p
        for p in LABELS_DIR.glob("*.xml")
    }

    print(f"Images found : {len(image_files)}")
    print(f"XML labels   : {len(xml_files)}")

    output_csv = OUTPUT_DIR / "plate_dataset.csv"

    rows = []
    csv_keys = set()

    with CSV_FILE.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        required_columns = {
            "Img_name",
            "width",
            "height",
            "depth",
            "xmin",
            "xmax",
            "ymin",
            "ymax",
            "license_number",
        }

        missing = required_columns - set(reader.fieldnames or [])

        if missing:
            raise ValueError(
                f"Missing CSV columns: {sorted(missing)}"
            )

        for csv_row in reader:
            xml_name = Path(csv_row["Img_name"]).name
            stem = Path(xml_name).stem.upper()

            csv_keys.add(stem)

            image_path = image_files.get(stem)
            xml_path = xml_files.get(stem)

            xml_data = parse_xml(xml_path) if xml_path else {
                "xml_valid": False,
                "xml_plate": "",
                "xmin": "",
                "ymin": "",
                "xmax": "",
                "ymax": "",
                "xml_error": "XML file not found",
            }

            csv_plate = normalize_plate(csv_row["license_number"])

            if image_path is None:
                status = "MISSING_IMAGE"
            elif xml_path is None:
                status = "MISSING_XML"
            elif (
                xml_data["xml_plate"]
                and xml_data["xml_plate"] != csv_plate
            ):
                status = "CSV_XML_PLATE_MISMATCH"
            else:
                status = "OK"

            rows.append(
                {
                    "image_id": stem,
                    "image_filename": image_path.name if image_path else "",
                    "image_path": (
                        str(image_path.relative_to(PROJECT_ROOT))
                        if image_path
                        else ""
                    ),
                    "xml_filename": xml_path.name if xml_path else "",
                    "xml_path": (
                        str(xml_path.relative_to(PROJECT_ROOT))
                        if xml_path
                        else ""
                    ),
                    "license_number": csv_plate,
                    "state_code": csv_plate[:2] if len(csv_plate) >= 2 else "",
                    "width": csv_row["width"],
                    "height": csv_row["height"],
                    "depth": csv_row["depth"],
                    "xmin": csv_row["xmin"],
                    "xmax": csv_row["xmax"],
                    "ymin": csv_row["ymin"],
                    "ymax": csv_row["ymax"],
                    "xml_license_number": xml_data["xml_plate"],
                    "status": status,
                }
            )

    fieldnames = [
        "image_id",
        "image_filename",
        "image_path",
        "xml_filename",
        "xml_path",
        "license_number",
        "state_code",
        "width",
        "height",
        "depth",
        "xmin",
        "xmax",
        "ymin",
        "ymax",
        "xml_license_number",
        "status",
    ]

    with output_csv.open(
        "w",
        encoding="utf-8",
        newline=""
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    extra_xml = sorted(set(xml_files) - csv_keys)

    status_counts = {}

    for row in rows:
        status = row["status"]
        status_counts[status] = status_counts.get(status, 0) + 1

    summary = {
        "images_found": len(image_files),
        "xml_labels_found": len(xml_files),
        "csv_records": len(rows),
        "extra_xml_without_csv_record": len(extra_xml),
        "extra_xml_files": extra_xml,
        "status_counts": status_counts,
    }

    summary_file = OUTPUT_DIR / "dataset_summary.json"

    with summary_file.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    report_file = RESULTS_DIR / "dataset_validation.txt"

    with report_file.open("w", encoding="utf-8") as file:
        file.write("TRUSTRAK AI DATASET VALIDATION\n")
        file.write("=" * 40 + "\n\n")

        file.write(f"Images found: {len(image_files)}\n")
        file.write(f"XML labels found: {len(xml_files)}\n")
        file.write(f"CSV records: {len(rows)}\n\n")

        file.write("STATUS COUNTS\n")
        file.write("-" * 40 + "\n")

        for status, count in sorted(status_counts.items()):
            file.write(f"{status}: {count}\n")

        file.write("\nEXTRA XML FILES WITHOUT CSV RECORD\n")
        file.write("-" * 40 + "\n")

        if extra_xml:
            for item in extra_xml:
                file.write(f"{item}.xml\n")
        else:
            file.write("None\n")

    print()
    print("Import completed.")
    print(f"Created: {output_csv}")
    print(f"Created: {summary_file}")
    print(f"Created: {report_file}")

    print()
    print("STATUS SUMMARY")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")

    print()
    if extra_xml:
        print("Extra XML files:")
        for item in extra_xml:
            print(f"  {item}.xml")
    else:
        print("No extra XML files found.")

    print("=" * 60)


if __name__ == "__main__":
    main()
