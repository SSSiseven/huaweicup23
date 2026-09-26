from pathlib import Path
import shutil

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def no_overlap(frame: pd.DataFrame, resource: str, end: str) -> bool:
    for _, group in frame.sort_values("start_s").groupby(resource):
        if any(group.iloc[i]["start_s"] < group.iloc[i - 1][end] - 1e-9 for i in range(1, len(group))):
            return False
    return True


def main() -> None:
    data = pd.read_csv(ROOT / "results" / "q2_transport_trips.csv")
    assert len(data) == 22
    assert no_overlap(data, "unit_id", "return_s")
    assert no_overlap(data, "battery_id", "battery_charge_complete_s")

    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "pdf.fonttype": 42,
    })
    colors = {"A": "#4C78A8", "B": "#F28E2B", "C": "#59A14F"}
    units = sorted(data["unit_id"].unique(), reverse=True)
    batteries = sorted(data["battery_id"].unique(), reverse=True)
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(10.2, 8.2), sharex=True,
        gridspec_kw={"height_ratios": [8, 14], "hspace": 0.12},
    )

    for y, unit in enumerate(units):
        for _, row in data[data["unit_id"] == unit].iterrows():
            start, takeoff, end = row["start_s"] / 3600, row["takeoff_s"] / 3600, row["return_s"] / 3600
            color = colors[row["type_id"]]
            ax1.barh(y, takeoff - start, left=start, height=0.62, color=color, alpha=0.35)
            ax1.barh(y, end - takeoff, left=takeoff, height=0.62, color=color, alpha=0.95)
            ax1.text((start + end) / 2, y, row["trip_id"], ha="center", va="center", fontsize=6.5)

    for y, battery in enumerate(batteries):
        for _, row in data[data["battery_id"] == battery].iterrows():
            start, end, charged = (
                row["start_s"] / 3600,
                row["return_s"] / 3600,
                row["battery_charge_complete_s"] / 3600,
            )
            color = colors[row["type_id"]]
            ax2.barh(y, end - start, left=start, height=0.62, color=color, alpha=0.95)
            ax2.barh(y, charged - end, left=end, height=0.62, color="#BDBDBD", alpha=0.75)
            ax2.text((start + end) / 2, y, row["trip_id"], ha="center", va="center", fontsize=6.2)

    ax1.set_yticks(range(len(units)), units)
    ax2.set_yticks(range(len(batteries)), batteries)
    ax1.set_ylabel("运输无人机")
    ax2.set_ylabel("共享电池")
    ax2.set_xlabel("时间 / h")
    makespan = data["return_s"].max() / 3600
    for ax in (ax1, ax2):
        ax.axvline(makespan, color="#C44E52", linestyle="--", linewidth=1.0)
        ax.grid(axis="x", color="#DDDDDD", linewidth=0.6)
        ax.set_axisbelow(True)
    ax1.text(makespan + 0.03, len(units) - 0.25, f"全部返航 {makespan:.3f} h", color="#A33A3E", fontsize=7.5)
    ax1.set_title("(a) 实体运输无人机占用", loc="left", fontsize=10)
    ax2.set_title("(b) 共享电池任务与充电占用", loc="left", fontsize=10)
    ax1.legend(
        handles=[
            mpatches.Patch(color="#4C78A8", label="A型任务"),
            mpatches.Patch(color="#F28E2B", label="B型任务"),
            mpatches.Patch(color="#59A14F", label="C型任务"),
            mpatches.Patch(color="#BDBDBD", label="返航后充电"),
        ],
        ncol=4, frameon=False, loc="upper right", fontsize=7.5,
    )
    fig.align_ylabels([ax1, ax2])
    fig.subplots_adjust(left=0.13, right=0.98, top=0.96, bottom=0.08)

    authority = ROOT / "figures" / "q2"
    paper = ROOT / "paper" / "figures" / "q2"
    authority.mkdir(parents=True, exist_ok=True)
    paper.mkdir(parents=True, exist_ok=True)
    for suffix in ("pdf", "png"):
        path = authority / f"q2_resource_gantt.{suffix}"
        fig.savefig(path, dpi=300 if suffix == "png" else None, bbox_inches="tight")
        shutil.copy2(path, paper / path.name)
    plt.close(fig)


if __name__ == "__main__":
    main()
