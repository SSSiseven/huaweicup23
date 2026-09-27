# AI 辅助说明：本程序及代码是在人工智能工具 OpenAI Codex（GPT-5，
# 开发机构 OpenAI，公开版本日期 2025-08-07）辅助下完成的；
# 图表数据与含义由参赛队结合原始结果复核。
from pathlib import Path
import shutil
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import solve_d  # noqa: E402


def main() -> None:
    data = solve_d.load_inputs(ROOT)
    dem, nodes, boxes, types = data["dem"], data["nodes"], data["boxes"], data["transport_types"]
    depot = nodes["O01"]
    batch_rows, plot_rows = [], []
    for service_id in sorted(k for k in nodes if k.startswith("S")):
        service_boxes = boxes[boxes["服务区编号"] == service_id]
        batches = solve_d.exact_q1_service(dem, depot, nodes[service_id], service_boxes, types)
        for idx, batch in enumerate(batches, 1):
            trip_id = f"Q1-{service_id}-{idx:02d}"
            drone = types[batch["type_id"]]
            row = {
                "trip_id": trip_id,
                "service_id": service_id,
                "type_id": batch["type_id"],
                "box_ids": ";".join(batch["box_ids"]),
                "mass_kg": batch["mass_kg"],
                "volume_m3": batch["volume_m3"],
                "duration_s": batch["duration_s"],
                "energy_kwh": batch["energy_kwh"],
                "return_soc": batch["return_soc"],
            }
            batch_rows.append(row)
            ratios = {
                "质量": batch["mass_kg"] / drone.payload_kg,
                "体积": batch["volume_m3"] / drone.volume_m3,
                "能量": batch["energy_kwh"] / ((1 - drone.reserve) * drone.energy_kwh),
            }
            plot_rows.append({
                **row,
                "box_count": len(batch["box_ids"]),
                "eta_mass": ratios["质量"],
                "eta_volume": ratios["体积"],
                "eta_energy": ratios["能量"],
                "tightest_constraint": max(ratios, key=ratios.get),
            })

    pd.DataFrame(batch_rows).to_csv(ROOT / "results" / "q1_batches.csv", index=False, encoding="utf-8-sig")
    frame = pd.DataFrame(plot_rows)
    frame.to_csv(ROOT / "results" / "q1_batch_utilization.csv", index=False, encoding="utf-8-sig")
    frame["plot_x"] = frame["eta_mass"] * 100
    frame["plot_y"] = frame["eta_volume"] * 100
    for _, group in frame.groupby(["eta_mass", "eta_volume"]):
        if len(group) > 1:
            angles = np.linspace(0, 2 * np.pi, len(group), endpoint=False)
            frame.loc[group.index, "plot_x"] += 1.15 * np.cos(angles)
            frame.loc[group.index, "plot_y"] += 1.15 * np.sin(angles)

    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "pdf.fonttype": 42,
    })
    fig, ax = plt.subplots(figsize=(7.0, 5.2))
    markers = {"A": "o", "B": "^", "C": "s"}
    image = None
    for type_id, marker in markers.items():
        part = frame[frame["type_id"] == type_id]
        if part.empty:
            continue
        image = ax.scatter(
            part["plot_x"],
            part["plot_y"],
            c=part["eta_energy"] * 100,
            s=35 + part["box_count"] * 13,
            marker=marker,
            cmap="viridis",
            vmin=0,
            vmax=100,
            edgecolors="#333333",
            linewidths=0.7,
            alpha=0.88,
            label=f"{type_id}型",
        )
    label_ids = {
        frame.loc[frame["eta_mass"].idxmax(), "trip_id"],
        frame.loc[frame["eta_volume"].idxmax(), "trip_id"],
        frame.loc[frame["eta_energy"].idxmax(), "trip_id"],
    }
    for _, row in frame.iterrows():
        if row["trip_id"] in label_ids:
            ax.annotate(
                row["trip_id"].replace("Q1-", ""),
                (row["plot_x"], row["plot_y"]),
                xytext=(4, 4), textcoords="offset points", fontsize=6.8,
            )
    ax.axvline(100, color="#777777", linestyle="--", linewidth=0.8)
    ax.axhline(100, color="#777777", linestyle="--", linewidth=0.8)
    ax.set_xlim(60, 103)
    ax.set_ylim(55, 103)
    ax.set_xlabel("额定载质量利用率 / %")
    ax.set_ylabel("舱容利用率 / %")
    ax.grid(True, color="#dddddd", linewidth=0.6, alpha=0.7)
    ax.legend(title="机型", frameon=False, loc="upper left")
    if image is not None:
        cbar = fig.colorbar(image, ax=ax, pad=0.02)
        cbar.set_label("安全可用能量利用率 / %")
    ax.text(0.0, -0.16, "注：坐标完全相同的批次作轻微错位显示。", transform=ax.transAxes,
            fontsize=7.5, color="#555555")
    fig.tight_layout()

    authority = ROOT / "figures" / "q1"
    paper = ROOT / "paper" / "figures" / "q1"
    authority.mkdir(parents=True, exist_ok=True)
    paper.mkdir(parents=True, exist_ok=True)
    for suffix in ("svg", "pdf", "png"):
        path = authority / f"q1_batch_utilization.{suffix}"
        fig.savefig(path, dpi=300 if suffix == "png" else None)
        shutil.copy2(path, paper / path.name)
    plt.close(fig)


if __name__ == "__main__":
    main()
