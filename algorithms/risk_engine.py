import csv
import heapq
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

REGISTRY_FILE = PROJECT_ROOT / "data" / "vehicle_registry.csv"
ANPR_FILE = PROJECT_ROOT / "data" / "anpr_events.csv"
FASTAG_FILE = PROJECT_ROOT / "data" / "fastag_events.csv"
MOVEMENT_FILE = PROJECT_ROOT / "data" / "movement_events.csv"

OUTPUT_FILE = PROJECT_ROOT / "data" / "verification_cases.csv"

MAX_PLAUSIBLE_KMH = 105
SLIDING_WINDOW_HOURS = 4


# ============================================================
# HASH MAP
# Registration number -> vehicle record
# Average lookup: O(1)
# ============================================================

class VehicleHashMap:
    def __init__(self):
        self.table = {}

    def build(self, registry_rows):
        for row in registry_rows:
            plate = row["registration_number"].strip().upper()
            self.table[plate] = row

    def get(self, plate):
        return self.table.get(
            plate.strip().upper()
        )

    def __contains__(self, plate):
        return plate.strip().upper() in self.table

    def __len__(self):
        return len(self.table)


# ============================================================
# GRAPH
# Weighted toll/road network
# ============================================================

class RoadGraph:
    def __init__(self):
        self.graph = defaultdict(list)

    def add_edge(self, a, b, distance_km):
        self.graph[a].append((b, distance_km))
        self.graph[b].append((a, distance_km))

    def shortest_distance(self, start, target):
        if start == target:
            return 0.0

        distances = {
            start: 0.0
        }

        pq = [
            (0.0, start)
        ]

        while pq:
            current_distance, node = heapq.heappop(pq)

            if node == target:
                return current_distance

            if current_distance > distances.get(
                node,
                float("inf")
            ):
                continue

            for neighbor, weight in self.graph[node]:
                new_distance = (
                    current_distance + weight
                )

                if new_distance < distances.get(
                    neighbor,
                    float("inf")
                ):
                    distances[neighbor] = new_distance
                    heapq.heappush(
                        pq,
                        (new_distance, neighbor)
                    )

        return None


def build_road_graph():
    graph = RoadGraph()

    graph.add_edge("Chennai", "Vellore", 140)
    graph.add_edge("Chennai", "Salem", 340)
    graph.add_edge("Vellore", "Salem", 205)
    graph.add_edge("Salem", "Trichy", 92)
    graph.add_edge("Salem", "Coimbatore", 158)
    graph.add_edge("Trichy", "Thanjavur", 58)
    graph.add_edge("Trichy", "Madurai", 132)
    graph.add_edge("Coimbatore", "Madurai", 211)
    graph.add_edge("Thanjavur", "Madurai", 88)
    graph.add_edge("Madurai", "Tirunelveli", 155)

    return graph


# ============================================================
# MAX HEAP
# Higher-risk cases come out first.
# ============================================================

class MaxHeap:
    def __init__(self):
        self.heap = []

    def push(self, score, item):
        heapq.heappush(
            self.heap,
            (-score, item)
        )

    def pop(self):
        if not self.heap:
            return None

        score, item = heapq.heappop(
            self.heap
        )

        return -score, item

    def __len__(self):
        return len(self.heap)


# ============================================================
# CSV HELPERS
# ============================================================

def read_csv(path):
    with path.open(
        "r",
        encoding="utf-8",
        newline=""
    ) as file:
        return list(
            csv.DictReader(file)
        )


def parse_timestamp(value):
    return datetime.fromisoformat(value)


def add_reason(case, reason, points):
    case["score"] += points

    if reason not in case["reasons"]:
        case["reasons"].append(reason)


# ============================================================
# MAIN ENGINE
# ============================================================

def main():
    print("=" * 70)
    print("TRUSTRAK AI - AADT INTEGRITY DETECTION ENGINE")
    print("=" * 70)

    registry_rows = read_csv(REGISTRY_FILE)
    anpr_rows = read_csv(ANPR_FILE)
    fastag_rows = read_csv(FASTAG_FILE)
    movement_rows = read_csv(MOVEMENT_FILE)

    # --------------------------------------------------------
    # 1. HASH MAP
    # --------------------------------------------------------

    vehicle_map = VehicleHashMap()
    vehicle_map.build(registry_rows)

    print()
    print("HASH MAP")
    print(
        f"Vehicle records indexed : {len(vehicle_map)}"
    )

    # --------------------------------------------------------
    # Case storage
    # --------------------------------------------------------

    cases = {}

    def get_case(plate):
        if plate not in cases:
            cases[plate] = {
                "registration_number": plate,
                "score": 0,
                "reasons": [],
                "evidence": [],
            }

        return cases[plate]

    # --------------------------------------------------------
    # 2. ANPR ANALYSIS
    # Hash Map + Sliding Window
    # --------------------------------------------------------

    events_by_plate = defaultdict(list)

    for row in anpr_rows:
        plate = row[
            "registration_number"
        ].strip().upper()

        events_by_plate[plate].append(row)

        vehicle = vehicle_map.get(plate)

        case = get_case(plate)

        # Unknown registration
        if vehicle is None:
            add_reason(
                case,
                "No registry match",
                40
            )

            case["evidence"].append(
                f"ANPR event {row['event_id']}"
            )

            continue

        # Vehicle type mismatch
        detected_type = row[
            "detected_vehicle_type"
        ].strip().lower()

        registered_type = vehicle[
            "vehicle_type"
        ].strip().lower()

        if (
            detected_type != "unknown"
            and detected_type != registered_type
        ):
            add_reason(
                case,
                (
                    "Vehicle type mismatch: "
                    f"registered {vehicle['vehicle_type']}, "
                    f"detected {row['detected_vehicle_type']}"
                ),
                30
            )

            case["evidence"].append(
                f"ANPR {row['event_id']}: vehicle type mismatch"
            )

        # Colour mismatch
        detected_colour = row[
            "detected_colour"
        ].strip().lower()

        registered_colour = vehicle[
            "registered_colour"
        ].strip().lower()

        if (
            detected_colour != "unknown"
            and detected_colour != registered_colour
        ):
            add_reason(
                case,
                (
                    "Colour mismatch: "
                    f"registered {vehicle['registered_colour']}, "
                    f"detected {row['detected_colour']}"
                ),
                20
            )

            case["evidence"].append(
                f"ANPR {row['event_id']}: colour mismatch"
            )

        # Permit status
        if vehicle["permit_status"] == "EXPIRED":
            add_reason(
                case,
                (
                    "Commercial permit expired"
                ),
                10
            )

        # Fitness
        if vehicle["fitness_status"] == "EXPIRED":
            add_reason(
                case,
                "Fitness certificate expired",
                10
            )

        # FASTag status
        if vehicle["fastag_status"] != "ACTIVE":
            add_reason(
                case,
                (
                    "FASTag status: "
                    f"{vehicle['fastag_status']}"
                ),
                10
            )

        # Suspended registry
        if vehicle["registry_status"] != "ACTIVE":
            add_reason(
                case,
                "Registry status is suspended",
                15
            )

    # --------------------------------------------------------
    # SLIDING WINDOW MOVEMENT ANALYSIS
    #
    # Keeps recent observations per registration.
    # Same plate returning to same location is not suspicious.
    # --------------------------------------------------------

    movement_anomalies = 0

    for plate, events in events_by_plate.items():
        events.sort(
            key=lambda row: parse_timestamp(
                row["timestamp"]
            )
        )

        window = deque()

        for current in events:
            current_time = parse_timestamp(
                current["timestamp"]
            )

            while window:
                old_time = parse_timestamp(
                    window[0]["timestamp"]
                )

                elapsed_hours = (
                    current_time - old_time
                ).total_seconds() / 3600

                if elapsed_hours <= SLIDING_WINDOW_HOURS:
                    break

                window.popleft()

            # Add current event after checking prior events.
            #
            # We do not penalize:
            # Chennai -> Chennai
            # or another same-location return.
            for previous in window:
                if (
                    previous["location"]
                    == current["location"]
                ):
                    continue

            window.append(current)

    # --------------------------------------------------------
    # 3. MOVEMENT + GRAPH ANALYSIS
    # --------------------------------------------------------

    road_graph = build_road_graph()

    for row in movement_rows:
        start = row[
            "from_location"
        ]

        end = row[
            "to_location"
        ]

        if (
            start not in road_graph.graph
            or end not in road_graph.graph
        ):
            continue

        departure = parse_timestamp(
            row["departure_time"]
        )

        arrival = parse_timestamp(
            row["arrival_time"]
        )

        elapsed_hours = (
            arrival - departure
        ).total_seconds() / 3600

        if elapsed_hours <= 0:
            continue

        distance = road_graph.shortest_distance(
            start,
            end
        )

        if distance is None:
            continue

        implied_speed = (
            distance / elapsed_hours
        )

        if implied_speed > MAX_PLAUSIBLE_KMH:
            plate = row[
                "registration_number"
            ].strip().upper()

            case = get_case(plate)

            add_reason(
                case,
                (
                    "Movement anomaly: "
                    f"{start} to {end}, "
                    f"{distance:.0f} km in "
                    f"{elapsed_hours:.2f} hours "
                    f"({implied_speed:.1f} km/h)"
                ),
                35
            )

            case["evidence"].append(
                f"Movement {row['movement_id']}"
            )

            movement_anomalies += 1

    # --------------------------------------------------------
    # 4. FASTAG ANALYSIS
    # --------------------------------------------------------

    for row in fastag_rows:
        plate = row[
            "registration_number"
        ].strip().upper()

        vehicle = vehicle_map.get(plate)

        case = get_case(plate)

        if vehicle is None:
            add_reason(
                case,
                "FASTag event linked to unknown plate",
                20
            )

            continue

        registered_fastag = vehicle[
            "fastag_id"
        ].strip()

        observed_fastag = row[
            "fastag_id"
        ].strip()

        if observed_fastag != registered_fastag:
            add_reason(
                case,
                (
                    "FASTag identity mismatch: "
                    f"registered {registered_fastag}, "
                    f"observed {observed_fastag}"
                ),
                30
            )

            case["evidence"].append(
                f"FASTag {row['transaction_id']}"
            )

        if row[
            "transaction_status"
        ] == "TAG_IDENTITY_MISMATCH":
            add_reason(
                case,
                "FASTag transaction identity mismatch",
                10
            )

    # --------------------------------------------------------
    # 5. NORMAL EVENT FILTER
    #
    # Don't create a case for a vehicle that has no signals.
    # --------------------------------------------------------

    filtered_cases = []

    for case in cases.values():

        if case["score"] <= 0:
            continue

        case["score"] = min(
            100,
            case["score"]
        )

        score = case["score"]

        if score >= 80:
            tier = "CRITICAL"
        elif score >= 60:
            tier = "HIGH"
        elif score >= 30:
            tier = "MEDIUM"
        else:
            tier = "LOW"

        case["risk_tier"] = tier
        case["status"] = "VERIFY"

        filtered_cases.append(case)

    # --------------------------------------------------------
    # 6. MAX HEAP PRIORITIZATION
    # --------------------------------------------------------

    priority_queue = MaxHeap()

    for case in filtered_cases:
        priority_queue.push(
            case["score"],
            case["registration_number"]
        )

    ranked = []

    rank = 1

    while len(priority_queue):
        result = priority_queue.pop()

        if result is None:
            break

        score, plate = result

        ranked.append(
            (
                rank,
                score,
                plate
            )
        )

        rank += 1

    # --------------------------------------------------------
    # 7. WRITE VERIFICATION CASES
    # --------------------------------------------------------

    case_lookup = {
        case["registration_number"]: case
        for case in filtered_cases
    }

    fields = [
        "case_id",
        "rank",
        "registration_number",
        "risk_score",
        "risk_tier",
        "status",
        "reasons",
        "evidence",
    ]

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

        for case_index, (
            rank_number,
            score,
            plate
        ) in enumerate(
            ranked,
            start=1
        ):
            case = case_lookup[plate]

            writer.writerow(
                {
                    "case_id": (
                        f"TR-2026-{case_index:05d}"
                    ),
                    "rank": rank_number,
                    "registration_number": plate,
                    "risk_score": score,
                    "risk_tier": case["risk_tier"],
                    "status": case["status"],
                    "reasons": " | ".join(
                        case["reasons"]
                    ),
                    "evidence": " | ".join(
                        case["evidence"]
                    ),
                }
            )

    # --------------------------------------------------------
    # CONSOLE REPORT
    # --------------------------------------------------------

    print()
    print("DSA ENGINE RESULTS")
    print("-" * 70)
    print(
        f"Unique vehicles indexed : {len(vehicle_map)}"
    )
    print(
        f"ANPR observations       : {len(anpr_rows)}"
    )
    print(
        f"FASTag observations     : {len(fastag_rows)}"
    )
    print(
        f"Movement observations   : {len(movement_rows)}"
    )
    print(
        f"Movement anomalies      : {movement_anomalies}"
    )
    print(
        f"Verification cases      : {len(filtered_cases)}"
    )

    print()
    print("TOP PRIORITY CASES")
    print("-" * 70)

    for rank_number, score, plate in ranked[:10]:
        case = case_lookup[plate]

        print(
            f"{rank_number:>2}. "
            f"{plate:<14} "
            f"Score={score:<3} "
            f"{case['risk_tier']:<8}"
        )

        for reason in case["reasons"][:3]:
            print(
                f"    - {reason}"
            )

    print()
    print(
        f"Output: {OUTPUT_FILE}"
    )

    print()
    print(
        "Detection engine completed."
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
