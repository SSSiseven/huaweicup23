"""Temporary/full-pipeline diagnostic for global relay-point coverage.

AI 辅助说明：本程序及代码是在人工智能工具 OpenAI Codex（GPT-5，
开发机构 OpenAI，版本发布日期 2025-08-07）辅助下完成的。
所有输出须由参赛者独立复核后使用。
"""
from pathlib import Path

import numpy as np
import pandas as pd

import solve_d


root = Path(__file__).resolve().parent
data = solve_d.load_inputs(root)
trips = pd.read_csv(root / "results" / "q2_transport_trips.csv")
boxes = data["boxes"]
indexed = boxes.set_index("货箱编号")
depot = data["nodes"]["O01"]
gateway = (
    depot.lon,
    depot.lat,
    depot.ground_m + data["comm"]["天线离地高度（m）"],
)
p1 = pd.read_csv(root / "results" / "p1_q3_relay.csv").iloc[0]
relay_point = (float(p1["lon"]), float(p1["lat"]), float(p1["altitude_m"]))
back = solve_d.interval_link_certificate(
    data["dem"], relay_point, relay_point, gateway,
    data["thresholds"]["relay_gateway"], data["comm"]["载波频率（MHz）"],
    data["comm"]["地形遮挡附加损耗（dB）"],
)
trajectory_by_trip = {}
rows = []
for _, trip in trips.iterrows():
    route = str(trip["route"]).split(";")
    box_ids = str(trip["box_ids"]).split(";")
    stops = [
        {"service_id": sid, "box_ids": [b for b in box_ids if indexed.loc[b, "服务区编号"] == sid]}
        for sid in route
    ]
    timeline = solve_d.route_timeline(
        data["dem"], depot, data["nodes"], data["transport_types"][trip["type_id"]],
        boxes, stops, float(trip["start_s"]),
    )
    phases = solve_d.route_trajectory(
        data["dem"], depot, data["nodes"], data["transport_types"][trip["type_id"]], timeline
    )
    trajectory_by_trip[str(trip["trip_id"])] = phases
    times = np.arange(phases[0]["t0"], phases[-1]["t1"] + 1e-9, 2.0)
    direct_bad = 0
    combined_bad = 0
    for t in times:
        pos = solve_d.position_at(phases, float(t))
        direct = solve_d.link_state(
            data["dem"], pos, gateway, data["thresholds"]["transport_gateway"],
            data["comm"]["载波频率（MHz）"], data["comm"]["地形遮挡附加损耗（dB）"],
        )
        direct_bad += int(not direct["available"])
        access = solve_d.link_state(
            data["dem"], pos, relay_point, data["thresholds"]["transport_relay"],
            data["comm"]["载波频率（MHz）"], data["comm"]["地形遮挡附加损耗（dB）"],
        )
        combined_bad += int(not direct["available"] and not (access["available"] and back["certified_available"]))
    rows.append({"trip_id": trip["trip_id"], "samples": len(times), "direct_bad": direct_bad,
                 "combined_bad": combined_bad, "route": trip["route"]})

print(pd.DataFrame(rows).to_string(index=False))
print("backhaul", back)

second = solve_d.find_static_relay(
    data["dem"], depot, data["relay_type"], trajectory_by_trip["T020"],
    data["comm"], data["thresholds"],
)
second_point = (second["lon"], second["lat"], second["altitude_m"])
second_back = solve_d.interval_link_certificate(
    data["dem"], second_point, second_point, gateway,
    data["thresholds"]["relay_gateway"], data["comm"]["载波频率（MHz）"],
    data["comm"]["地形遮挡附加损耗（dB）"],
)
pair_rows = []
for trip_id, phases in trajectory_by_trip.items():
    times = np.arange(phases[0]["t0"], phases[-1]["t1"] + 1e-9, 2.0)
    bad = 0
    for t in times:
        pos = solve_d.position_at(phases, float(t))
        states = [solve_d.link_state(
            data["dem"], pos, fixed, threshold,
            data["comm"]["载波频率（MHz）"], data["comm"]["地形遮挡附加损耗（dB）"],
        )["available"] for fixed, threshold in (
            (gateway, data["thresholds"]["transport_gateway"]),
            (relay_point, data["thresholds"]["transport_relay"]),
            (second_point, data["thresholds"]["transport_relay"]),
        )]
        bad += int(not any(states))
    pair_rows.append({"trip_id": trip_id, "pair_bad": bad})
print("second", second)
print(pd.DataFrame(pair_rows).to_string(index=False))

# Search one complement point for the three initially simultaneous urgent routes
# that the first relay does not fully cover.
uncovered = []
for trip_id in ("T002", "T004", "T008"):
    phases = trajectory_by_trip[trip_id]
    for t in np.arange(phases[0]["t0"], phases[-1]["t1"] + 1e-9, 4.0):
        pos = solve_d.position_at(phases, float(t))
        direct = solve_d.link_state(data["dem"], pos, gateway,
            data["thresholds"]["transport_gateway"], data["comm"]["载波频率（MHz）"],
            data["comm"]["地形遮挡附加损耗（dB）"])
        first = solve_d.link_state(data["dem"], pos, relay_point,
            data["thresholds"]["transport_relay"], data["comm"]["载波频率（MHz）"],
            data["comm"]["地形遮挡附加损耗（dB）"])
        if not direct["available"] and not first["available"]:
            uncovered.append(pos)

dem = data["dem"]
lons = [p[0] for p in uncovered] + [depot.lon]
lats = [p[1] for p in uncovered] + [depot.lat]
r0, c0 = dem.row_col(min(lons) - 0.025, max(lats) + 0.025)
r1, c1 = dem.row_col(max(lons) + 0.025, min(lats) - 0.025)
r0, r1 = max(0, min(r0, r1)), min(dem.height - 1, max(r0, r1))
c0, c1 = max(0, min(c0, c1)), min(dem.width - 1, max(c0, c1))
best = None
for row in range(r0, r1 + 1, 18):
    for col in range(c0, c1 + 1, 18):
        lon = dem.lon0 + col * dem.dx
        lat = dem.lat0 - row * dem.dy
        ground = float(dem.values[row, col])
        for agl in (150.0, 225.0, 300.0):
            point = (lon, lat, ground + agl)
            bh = solve_d.link_state(dem, point, gateway, data["thresholds"]["relay_gateway"],
                data["comm"]["载波频率（MHz）"], data["comm"]["地形遮挡附加损耗（dB）"])
            if not bh["available"]:
                continue
            states = [solve_d.link_state(dem, p, point, data["thresholds"]["transport_relay"],
                data["comm"]["载波频率（MHz）"], data["comm"]["地形遮挡附加损耗（dB）"])
                for p in uncovered]
            coverage = sum(x["available"] for x in states)
            min_margin = min([bh["margin_db"]] + [x["margin_db"] for x in states])
            score = (-coverage, -min_margin, lon, lat, agl)
            if best is None or score < best[0]:
                best = (score, point, coverage, min_margin)
print("complement", best, "uncovered_count", len(uncovered))
