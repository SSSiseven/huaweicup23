"""Minimal contract test for Q4 relay ownership.

AI 辅助说明：本程序及代码是在人工智能工具 OpenAI Codex 辅助下完成的；
参赛者须独立复核后使用。
"""

from solve_d import _solve_q4_partitions


def mission(mid: str, served: list[str], offset: float) -> dict:
    return {
        "mission_id": mid,
        "served_trip_ids": served,
        "start_s": offset,
        "return_s": offset + 8.0,
        "available_s": offset + 10.0,
        "pack_charge_complete_s": offset + 12.0,
    }


def trip(tid: str, service: str, type_id: str, offset: float) -> dict:
    return {
        "trip_id": tid,
        "route": [service],
        "type_id": type_id,
        "start_s": offset,
        "return_s": offset + 5.0,
        "battery_charge_complete_s": offset + 7.0,
    }


data = {
    "nodes": {"O01": object(), "S001": object(), "S002": object(), "S003": object()},
    "relay_inventory": {"units": 2, "packs": 6},
}
trips = [
    trip("T001", "S001", "A", 0.0),
    trip("T002", "S002", "B", 0.0),
    trip("T003", "S003", "C", 0.0),
]
# Every mission lists all wave trips as candidates, but the final segmentation
# assigns exactly one mission to each trip.
missions = [
    mission("R-001", ["T001", "T002", "T003"], 0.0),
    mission("R-002", ["T001", "T002", "T003"], 0.0),
    mission("R-003", ["T001", "T002", "T003"], 0.0),
]
segments = [
    {"trip_id": "T001", "relay_mission_id": "R-001"},
    {"trip_id": "T002", "relay_mission_id": "R-002"},
    {"trip_id": "T003", "relay_mission_id": "R-003"},
]

rows, _ = _solve_q4_partitions(data, trips, missions, segments)
k3 = [row for row in rows if row["K"] == 3]
assert len(k3) == 3
assert {row["relay_uav"] for row in k3} == {1}
assert {row["relay_pack"] for row in k3} == {1}
print("PASS: Q4 relay ownership follows actual communication assignments")
