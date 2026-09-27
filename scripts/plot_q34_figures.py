# AI 辅助说明：本程序及代码是在人工智能工具 OpenAI Codex（GPT-5，
# 开发机构 OpenAI，公开版本日期 2025-08-07）辅助下完成的；
# 图表数据与含义由参赛队结合原始结果复核。
from pathlib import Path
import shutil

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import solve_d


COLORS = ["#4C78A8", "#F28E2B", "#59A14F", "#E15759", "#B07AA1", "#76B7B2"]


def save(fig, name: str) -> None:
    authority = ROOT / "figures" / "q3_q4"
    paper = ROOT / "paper" / "figures" / "q3_q4"
    authority.mkdir(parents=True, exist_ok=True)
    paper.mkdir(parents=True, exist_ok=True)
    for suffix in ("svg", "pdf", "png"):
        path = authority / f"{name}.{suffix}"
        fig.savefig(path, dpi=300 if suffix == "png" else None)
        shutil.copy2(path, paper / path.name)
    plt.close(fig)


def plot_phase(missions: pd.DataFrame) -> None:
    prep_fly = (missions.link_ready_s - missions.start_s) / 60
    service = (missions.service_end_s - missions.link_ready_s) / 60
    returning = (missions.return_s - missions.service_end_s) / 60
    y = np.arange(len(missions))
    fig, ax = plt.subplots(figsize=(8.4, 5.0))
    ax.barh(y, prep_fly, color="#9ECAE1", label="准备、飞抵与建链")
    ax.barh(y, service, left=prep_fly, color="#3182BD", label="在位保障")
    ax.barh(y, returning, left=prep_fly + service, color="#BDBDBD", label="返航")
    ax.set_yticks(y, missions.mission_id)
    ax.invert_yaxis()
    ax.set_xlabel("持续时间 / min")
    ax.grid(axis="x", color="#E1E1E1", linewidth=0.6)
    ax.legend(frameon=False, ncol=3, loc="lower right")
    fig.tight_layout()
    save(fig, "raw_q3_relay_phase_duration")


def plot_relay_gantt(missions: pd.DataFrame) -> None:
    units = sorted(missions.relay_unit_id.unique())
    fig, ax = plt.subplots(figsize=(9.2, 3.2))
    for y, unit in enumerate(units):
        for _, row in missions[missions.relay_unit_id == unit].iterrows():
            start, ready, end, available = [row[x] / 3600 for x in ("start_s", "link_ready_s", "service_end_s", "available_s")]
            ax.barh(y, ready - start, left=start, height=0.55, color="#9ECAE1")
            ax.barh(y, end - ready, left=ready, height=0.55, color="#3182BD")
            ax.barh(y, available - end, left=end, height=0.55, color="#BDBDBD")
            ax.text((start + available) / 2, y, row.mission_id, ha="center", va="center", fontsize=7)
    ax.set_yticks(range(len(units)), units)
    ax.set_xlabel("时间 / h")
    ax.set_ylabel("中继无人机")
    ax.grid(axis="x", color="#E1E1E1", linewidth=0.6)
    ax.legend(handles=[
        mpatches.Patch(color="#9ECAE1", label="准备、飞抵与建链"),
        mpatches.Patch(color="#3182BD", label="在位保障"),
        mpatches.Patch(color="#BDBDBD", label="返航与周转"),
    ], frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.18))
    fig.tight_layout()
    save(fig, "process_q3_relay_gantt")


def plot_comm_timeline(segments: pd.DataFrame) -> None:
    trips = sorted(segments.trip_id.unique(), reverse=True)
    fig, ax = plt.subplots(figsize=(9.4, 6.8))
    for y, trip in enumerate(trips):
        for _, row in segments[segments.trip_id == trip].iterrows():
            start, end = row.start_s / 3600, row.end_s / 3600
            relay = row.assurance == "中继"
            ax.barh(y, end - start, left=start, height=0.58,
                    color="#F28E2B" if relay else "#4C78A8",
                    hatch="///" if relay else None, edgecolor="white", linewidth=0.2)
    ax.set_yticks(range(len(trips)), trips)
    ax.set_xlabel("时间 / h")
    ax.set_ylabel("运输架次")
    ax.grid(axis="x", color="#E1E1E1", linewidth=0.6)
    ax.legend(handles=[
        mpatches.Patch(color="#4C78A8", label="直连"),
        mpatches.Patch(facecolor="#F28E2B", hatch="///", label="中继"),
    ], frameon=False, ncol=2, loc="lower right")
    fig.tight_layout()
    save(fig, "result_q3_communication_timeline")


def components_from_routes(trips: pd.DataFrame) -> tuple[list[list[str]], list[tuple[str, str]]]:
    services = [f"S{i:03d}" for i in range(1, 16)]
    parent = {x: x for x in services}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[max(a, b)] = min(a, b)
    edges = []
    for route in trips.route.astype(str):
        nodes = route.split(";")
        for a, b in zip(nodes, nodes[1:]):
            union(a, b)
            edges.append((a, b))
    groups = {}
    for service in services:
        groups.setdefault(find(service), []).append(service)
    return sorted(groups.values()), edges


def plot_atoms(data: dict, trips: pd.DataFrame) -> None:
    components, edges = components_from_routes(trips)
    fig, ax = plt.subplots(figsize=(7.2, 5.5))
    for a, b in edges:
        na, nb = data["nodes"][a], data["nodes"][b]
        ax.plot([na.lon, nb.lon], [na.lat, nb.lat], color="#A0A0A0", linewidth=1.2, zorder=1)
    for i, component in enumerate(components):
        xs = [data["nodes"][x].lon for x in component]
        ys = [data["nodes"][x].lat for x in component]
        ax.scatter(xs, ys, s=55, color=COLORS[i % len(COLORS)], zorder=2)
        for x, lon, lat in zip(component, xs, ys):
            ax.annotate(x, (lon, lat), xytext=(4, 4), textcoords="offset points", fontsize=7)
    ax.set_xlabel("经度 / °E")
    ax.set_ylabel("纬度 / °N")
    ax.grid(color="#E6E6E6", linewidth=0.5)
    fig.tight_layout()
    save(fig, "raw_q4_atomic_components")


def plot_tradeoff(summary: pd.DataFrame) -> None:
    labels = ["A机", "B机", "C机", "A电池", "B电池", "C电池", "中继机", "中继组件"]
    keys = ["A_uav", "B_uav", "C_uav", "A_battery", "B_battery", "C_battery", "relay_uav", "relay_pack"]
    x = np.arange(len(keys))
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 3.8), sharey=True)
    for ax, k in zip(axes, (2, 3)):
        part = summary[summary.K == k].set_index("resource").loc[keys]
        ax.bar(x - 0.18, part.shortfall, width=0.36, color="#E15759", label="库存缺口")
        ax.bar(x + 0.18, part.partition_redundancy, width=0.36, color="#4C78A8", label="分区冗余")
        ax.set_xticks(x, labels, rotation=35, ha="right")
        ax.set_title(f"$K={k}$")
        ax.set_ylabel("资源数量")
        ax.set_ylim(0, max(1.25, float(summary[["shortfall", "partition_redundancy"]].max().max()) + 0.5))
        ax.grid(axis="y", color="#E1E1E1", linewidth=0.6)
        if not part[["shortfall", "partition_redundancy"]].to_numpy().any():
            ax.text(0.5, 0.52, "各类资源缺口与分区冗余均为 0",
                    transform=ax.transAxes, ha="center", va="center", color="#555555")
    axes[1].legend(frameon=False, loc="upper right")
    fig.tight_layout()
    save(fig, "process_q4_resource_tradeoff")


def plot_partition_map(data: dict, partitions: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.2), sharex=True, sharey=True)
    for ax, k in zip(axes, (2, 3)):
        part = partitions[partitions.K == k]
        for _, row in part.iterrows():
            services = str(row.services).split(";")
            xs = [data["nodes"][x].lon for x in services]
            ys = [data["nodes"][x].lat for x in services]
            color = COLORS[int(row.group) - 1]
            ax.scatter(xs, ys, s=58, color=color, label=f"第{int(row.group)}组")
            for service, lon, lat in zip(services, xs, ys):
                ax.annotate(service, (lon, lat), xytext=(3, 3), textcoords="offset points", fontsize=6.5)
        ax.set_title(f"$K={k}$")
        ax.set_xlabel("经度 / °E")
        ax.grid(color="#E6E6E6", linewidth=0.5)
        ax.legend(frameon=False, fontsize=8)
    axes[0].set_ylabel("纬度 / °N")
    fig.tight_layout()
    save(fig, "result_q4_partition_map")


def main() -> None:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "pdf.fonttype": 42,
    })
    missions = pd.read_csv(ROOT / "results" / "q3_relay_missions.csv")
    segments = pd.read_csv(ROOT / "results" / "q3_communication_segments.csv")
    trips = pd.read_csv(ROOT / "results" / "q3_transport_trips.csv")
    partitions = pd.read_csv(ROOT / "results" / "q4_partition_resources.csv")
    summary = pd.read_csv(ROOT / "results" / "q4_shortage_redundancy.csv")
    data = solve_d.load_inputs(ROOT)
    assert len(trips) == 22 and not (segments.assurance == "未证明").any()
    plot_phase(missions)
    plot_relay_gantt(missions)
    plot_comm_timeline(segments)
    plot_atoms(data, trips)
    plot_tradeoff(summary)
    plot_partition_map(data, partitions)


if __name__ == "__main__":
    main()
