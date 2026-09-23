"""Search a two-static-relay cover for simultaneous 3600 s hard-deadline routes.

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
gateway = (depot.lon, depot.lat, depot.ground_m + data["comm"]["天线离地高度（m）"])
freq = data["comm"]["载波频率（MHz）"]
obs = data["comm"]["地形遮挡附加损耗（dB）"]

positions = []
for _, trip in trips.iloc[12:15].iterrows():
    route = str(trip["route"]).split(";")
    box_ids = str(trip["box_ids"]).split(";")
    stops = [{"service_id": sid,
              "box_ids": [b for b in box_ids if indexed.loc[b, "服务区编号"] == sid]}
             for sid in route]
    timeline = solve_d.route_timeline(data["dem"], depot, data["nodes"],
        data["transport_types"][trip["type_id"]], boxes, stops, float(trip["start_s"]))
    phases = solve_d.route_trajectory(data["dem"], depot, data["nodes"],
        data["transport_types"][trip["type_id"]], timeline)
    for t in np.arange(phases[0]["t0"], phases[-1]["t1"] + 1e-9, 5.0):
        pos = solve_d.position_at(phases, float(t))
        direct = solve_d.link_state(data["dem"], pos, gateway,
            data["thresholds"]["transport_gateway"], freq, obs)
        if not direct["available"]:
            positions.append(pos)

dem = data["dem"]
lons = [p[0] for p in positions] + [depot.lon]
lats = [p[1] for p in positions] + [depot.lat]
r0, c0 = dem.row_col(min(lons) - 0.03, max(lats) + 0.03)
r1, c1 = dem.row_col(max(lons) + 0.03, min(lats) - 0.03)
r0, r1 = max(0, min(r0, r1)), min(dem.height - 1, max(r0, r1))
c0, c1 = max(0, min(c0, c1)), min(dem.width - 1, max(c0, c1))
full = (1 << len(positions)) - 1
candidates = []
for row in range(r0, r1 + 1, 24):
    for col in range(c0, c1 + 1, 24):
        lon = dem.lon0 + col * dem.dx
        lat = dem.lat0 - row * dem.dy
        ground = float(dem.values[row, col])
        for agl in (225.0, 300.0):
            point = (lon, lat, ground + agl)
            back = solve_d.link_state(dem, point, gateway,
                data["thresholds"]["relay_gateway"], freq, obs)
            if not back["available"]:
                continue
            bits = 0
            margins = [back["margin_db"]]
            for i, pos in enumerate(positions):
                state = solve_d.link_state(dem, pos, point,
                    data["thresholds"]["transport_relay"], freq, obs)
                if state["available"]:
                    bits |= 1 << i
                margins.append(state["margin_db"])
            candidates.append({"point": point, "bits": bits, "count": bits.bit_count(),
                               "min_margin": min(margins)})

# Keep the strongest coverage masks; duplicate masks retain the higher-margin point.
by_mask = {}
for candidate in candidates:
    previous = by_mask.get(candidate["bits"])
    if previous is None or candidate["min_margin"] > previous["min_margin"]:
        by_mask[candidate["bits"]] = candidate
candidates = sorted(by_mask.values(), key=lambda x: (-x["count"], -x["min_margin"]))[:500]
best = None
for i, first in enumerate(candidates):
    for second in candidates[i:]:
        union = first["bits"] | second["bits"]
        score = (-(union.bit_count()), -(min(first["min_margin"], second["min_margin"])),
                 first["point"], second["point"])
        if best is None or score < best[0]:
            best = (score, first, second, union)
        if union == full:
            break
    if best is not None and best[3] == full:
        break

print("positions", len(positions), "raw_candidates", len(candidates))
print("best_union", best[3].bit_count(), "full", len(positions))
print("point1", best[1])
print("point2", best[2])
