# AI 辅助说明：本程序及代码是在人工智能工具 OpenAI Codex（GPT-5，
# 开发机构 OpenAI，公开版本日期 2025-08-07）辅助下完成的；
# 图表数据与含义由参赛队结合原始结果复核。
from pathlib import Path
import shutil

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import solve_d  # noqa: E402


def main() -> None:
    data = solve_d.load_inputs(ROOT)
    rows = []
    for service_id in sorted(k for k in data["nodes"] if k.startswith("S")):
        for type_id, drone in data["transport_types"].items():
            safe = solve_d.max_safe_payload(
                data["dem"], data["nodes"]["O01"], data["nodes"][service_id], drone
            )
            rows.append(
                {
                    "service_id": service_id,
                    "type_id": type_id,
                    "safe_payload_kg": safe,
                    "payload_ratio_pct": 100 * safe / drone.payload_kg,
                }
            )

    frame = pd.DataFrame(rows)
    frame[["service_id", "type_id", "safe_payload_kg"]].to_csv(
        ROOT / "results" / "q1_safe_payload.csv", index=False, encoding="utf-8-sig"
    )
    value = frame.pivot(index="type_id", columns="service_id", values="payload_ratio_pct")
    payload = frame.pivot(index="type_id", columns="service_id", values="safe_payload_kg")
    value = value.loc[["A", "B", "C"]]
    payload = payload.loc[["A", "B", "C"]]

    labels = payload.copy().astype(object)
    rated = {"A": 25.0, "B": 30.0, "C": 80.0}
    for drone in labels.index:
        for service in labels.columns:
            x = payload.loc[drone, service]
            labels.loc[drone, service] = (
                "不可达" if pd.isna(x) else f"{x:.1f}" + ("●" if abs(x - rated[drone]) < 1e-6 else "")
            )

    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "pdf.fonttype": 42,
    })
    fig, ax = plt.subplots(figsize=(10.2, 2.65))
    values = value.to_numpy(dtype=float)
    vmin = max(0, np.floor(np.nanmin(values) / 5) * 5)
    image = ax.imshow(values, cmap="YlGnBu", vmin=vmin, vmax=100, aspect="auto")
    ax.set_xticks(range(len(value.columns)), value.columns)
    ax.set_yticks(range(3), ["A型", "B型", "C型"])
    ax.set_xticks(np.arange(-0.5, len(value.columns), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, 3, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=0.8)
    ax.tick_params(which="minor", bottom=False, left=False)
    for i in range(3):
        for j in range(len(value.columns)):
            color = "white" if values[i, j] > (vmin + 100) / 2 else "black"
            ax.text(j, i, labels.iloc[i, j], ha="center", va="center", fontsize=7.2, color=color)
    cbar = fig.colorbar(image, ax=ax, shrink=0.82, pad=0.015)
    cbar.set_label("安全载荷保持率 / %")
    ax.set_xlabel("服务区")
    ax.set_ylabel("运输无人机机型")
    ax.tick_params(axis="x", rotation=35, labelsize=8)
    ax.tick_params(axis="y", labelsize=9)
    ax.text(
        0.0, -0.43, "注：格内数字为最大安全载荷（kg）；●表示达到机型额定载荷。",
        transform=ax.transAxes, fontsize=8, color="#444444"
    )
    fig.tight_layout()

    authority = ROOT / "figures" / "q1"
    paper = ROOT / "paper" / "figures" / "q1"
    authority.mkdir(parents=True, exist_ok=True)
    paper.mkdir(parents=True, exist_ok=True)
    for suffix in ("svg", "pdf", "png"):
        path = authority / f"q1_safe_payload_heatmap.{suffix}"
        fig.savefig(path, dpi=300 if suffix == "png" else None)
        shutil.copy2(path, paper / path.name)
    plt.close(fig)


if __name__ == "__main__":
    main()
