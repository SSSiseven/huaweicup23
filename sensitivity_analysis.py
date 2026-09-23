#!/usr/bin/env python3
"""Deterministic sensitivity analyses for the 2026 Huawei Cup D solution.

AI 辅助说明：本程序及代码是在人工智能工具 OpenAI Codex（GPT-5，
开发机构 OpenAI，版本发布日期 2025-08-07）辅助下完成的。
所有模型、参数、输出均须由参赛者独立复核后使用。
"""
from dataclasses import replace
from pathlib import Path
import json

import numpy as np
import pandas as pd

import solve_d


root = Path(__file__).resolve().parent
results = root / "results"
data = solve_d.load_inputs(root)
nodes, boxes, dem = data["nodes"], data["boxes"], data["dem"]
depot = nodes["O01"]

summary_rows = []
safe_rows = []
for reserve in (0.10, 0.15, 0.20, 0.25, 0.30):
    types = {key: replace(value, reserve=reserve) for key, value in data["transport_types"].items()}
    batches_all = []
    for service_id in sorted(key for key in nodes if key.startswith("S")):
        service_boxes = boxes[boxes["服务区编号"] == service_id]
        batches = solve_d.exact_q1_service(dem, depot, nodes[service_id], service_boxes, types)
        batches_all.extend(batches)
        for type_id, drone_type in types.items():
            safe_rows.append(
                {"reserve": reserve, "service_id": service_id, "type_id": type_id,
                 "safe_payload_kg": solve_d.max_safe_payload(
                     dem, depot, nodes[service_id], drone_type
                 )}
            )
    summary_rows.append(
        {"reserve": reserve, "trip_count": len(batches_all),
         "energy_kwh": sum(x["energy_kwh"] for x in batches_all),
         "duration_s": sum(x["duration_s"] for x in batches_all),
         "min_return_soc": min(x["return_soc"] for x in batches_all)}
    )

pd.DataFrame(summary_rows).to_csv(results / "sensitivity_q1_reserve.csv", index=False, encoding="utf-8-sig")
pd.DataFrame(safe_rows).to_csv(results / "sensitivity_q1_safe_payload.csv", index=False, encoding="utf-8-sig")

q2_delivery = pd.read_csv(results / "q2_box_deliveries.csv")
hard = q2_delivery[q2_delivery["hard_deadline_s"].notna()].copy()
delay_rows = []
for delay_s in range(0, 1201, 60):
    shifted = hard["completion_s"] + delay_s
    delay_rows.append(
        {"ground_delay_s": delay_s,
         "hard_late_count": int((shifted > hard["hard_deadline_s"] + 1e-9).sum()),
         "min_hard_slack_s": float((hard["hard_deadline_s"] - shifted).min())}
    )
pd.DataFrame(delay_rows).to_csv(results / "sensitivity_q2_delay.csv", index=False, encoding="utf-8-sig")

full = json.loads((results / "full_results.json").read_text(encoding="utf-8"))
proof_margins = np.asarray([x["min_margin_lower_db"] for x in full["q3"]["proofs"]])
robust_rows = []
for extra_margin_db in (0.0, 0.1, 0.2, 0.5, 1.0, 2.0):
    robust_rows.append(
        {"extra_margin_db": extra_margin_db,
         "certified_trip_count": int(np.sum(proof_margins >= extra_margin_db - 1e-12)),
         "uncertified_trip_count": int(np.sum(proof_margins < extra_margin_db - 1e-12)),
         "worst_adjusted_margin_db": float(proof_margins.min() - extra_margin_db)}
    )
pd.DataFrame(robust_rows).to_csv(results / "sensitivity_q3_margin.csv", index=False, encoding="utf-8-sig")

print(pd.DataFrame(summary_rows).to_string(index=False))
print(pd.DataFrame(delay_rows).tail().to_string(index=False))
print(pd.DataFrame(robust_rows).to_string(index=False))
