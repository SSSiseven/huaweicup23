"""Focused certificate refinement for T019.

AI 辅助说明：本程序及代码是在人工智能工具 OpenAI Codex（GPT-5，
开发机构 OpenAI，版本发布日期 2025-08-07）辅助下完成的。
所有输出须由参赛者独立复核后使用。
"""
from pathlib import Path
import pandas as pd
import solve_d

root = Path(__file__).resolve().parent
d = solve_d.load_inputs(root)
trips = pd.read_csv(root / "results" / "q3_transport_trips.csv")
row = trips[trips.trip_id == "T019"].iloc[0]
trip = row.to_dict()
trip["route"] = str(row.route).split(";")
trip["box_ids"] = str(row.box_ids).split(";")
stops = solve_d._trip_stops_from_record(trip, d["boxes"])
timeline = solve_d.route_timeline(d["dem"], d["nodes"]["O01"], d["nodes"],
    d["transport_types"][row.type_id], d["boxes"], stops, float(row.start_s))
phases = solve_d.route_trajectory(d["dem"], d["nodes"]["O01"], d["nodes"],
    d["transport_types"][row.type_id], timeline)
known = {
    "P1A": (109.28277777777778, 23.026944444444446, 649.4981079101562),
    "P1B": (109.22277777777778, 23.040277777777778, 587.5166015625),
    "P2A": (109.20555555555556, 23.049444444444443, 703.3844604492188),
    "P2B": (109.22555555555556, 23.069444444444446, 626.3524169921875),
    "P3A": (109.23833333333333, 23.052777777777777, 534.8773498535156),
}
import itertools
for names in itertools.combinations(known, 2):
    proof = solve_d.adaptive_multi_relay_check(d["dem"], d["nodes"]["O01"], phases,
        [known[x] for x in names], d["comm"], d["thresholds"], tol_s=0.1, grid_step_s=2.0)
    print(names, proof["unresolved_intervals"], proof["grid_outages"], proof["min_margin_lower_db"])
