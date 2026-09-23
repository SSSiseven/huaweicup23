"""Audit fixed two-relay sample coverage over all Q2 routes.

AI 辅助说明：本程序及代码是在人工智能工具 OpenAI Codex（GPT-5，
开发机构 OpenAI，版本发布日期 2025-08-07）辅助下完成的。
所有输出须由参赛者独立复核后使用。
"""
from pathlib import Path
import numpy as np
import pandas as pd
import solve_d

root = Path(__file__).resolve().parent
d = solve_d.load_inputs(root)
trips = pd.read_csv(root / "results" / "q2_transport_trips.csv")
b = d["boxes"]
idx = b.set_index("货箱编号")
o = d["nodes"]["O01"]
gateway = (o.lon, o.lat, o.ground_m + d["comm"]["天线离地高度（m）"])
points = [(109.28277777777778, 23.026944444444446, 649.4981079101562),
          (109.22277777777778, 23.040277777777778, 587.5166015625)]
freq, obs = d["comm"]["载波频率（MHz）"], d["comm"]["地形遮挡附加损耗（dB）"]
for _, trip in trips.iterrows():
    route, ids = str(trip.route).split(";"), str(trip.box_ids).split(";")
    stops = [{"service_id": s, "box_ids": [x for x in ids if idx.loc[x, "服务区编号"] == s]} for s in route]
    tl = solve_d.route_timeline(d["dem"], o, d["nodes"], d["transport_types"][trip.type_id], b, stops, float(trip.start_s))
    phases = solve_d.route_trajectory(d["dem"], o, d["nodes"], d["transport_types"][trip.type_id], tl)
    bad = 0
    for t in np.arange(phases[0]["t0"], phases[-1]["t1"] + 1e-9, 2.0):
        pos = solve_d.position_at(phases, float(t))
        available = solve_d.link_state(d["dem"], pos, gateway, d["thresholds"]["transport_gateway"], freq, obs)["available"]
        for point in points:
            available = available or solve_d.link_state(d["dem"], pos, point, d["thresholds"]["transport_relay"], freq, obs)["available"]
        bad += int(not available)
    print(trip.trip_id, bad)
