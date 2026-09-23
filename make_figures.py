"""Generate the 12 audited paper figure groups from frozen solver outputs.

All numerical marks are loaded from the original attachments or results/*.csv.
Each logical figure is exported as a 300 dpi PNG and an editable SVG.

AI 辅助说明：本程序及代码是在人工智能工具 OpenAI Codex（GPT-5，
开发机构 OpenAI，版本发布日期 2025-08-07）辅助下完成的。
所有图表、数据和结论均须由参赛者独立复核后使用。
"""

from __future__ import annotations

from pathlib import Path
import math

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd
from PIL import Image
from matplotlib.ticker import MaxNLocator

import solve_d


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
FIGURES.mkdir(exist_ok=True)

COLORS = {
    "blue": "#2878B5",
    "orange": "#F28E2B",
    "green": "#59A14F",
    "red": "#E15759",
    "purple": "#8E6C8A",
    "cyan": "#4EACC5",
    "gray": "#777777",
    "gold": "#EDC948",
}


def setup_style() -> None:
    candidates = ["Microsoft YaHei", "SimSun", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS"]
    installed = {f.name for f in font_manager.fontManager.ttflist}
    zh_font = next((name for name in candidates if name in installed), "DejaVu Sans")
    mpl.rcParams.update(
        {
            "font.family": zh_font,
            "axes.unicode_minus": False,
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "figure.dpi": 120,
            "savefig.dpi": 300,
            "svg.fonttype": "none",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.22,
            "grid.linewidth": 0.6,
        }
    )


def save(fig: plt.Figure, stem: str) -> None:
    fig.savefig(FIGURES / f"{stem}.png", dpi=300, facecolor="white")
    fig.savefig(FIGURES / f"{stem}.svg", facecolor="white")
    plt.close(fig)


def distance_m(a, b) -> float:
    return solve_d.horizontal_distance_m(a.lon, a.lat, b.lon, b.lat)


def union_components(service_ids: list[str], routes: list[str]) -> dict[str, int]:
    parent = {s: s for s in service_ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for route in routes:
        items = [x for x in str(route).split(";") if x]
        for s in items[1:]:
            union(items[0], s)
    roots = {r: i for i, r in enumerate(sorted({find(s) for s in service_ids}), 1)}
    return {s: roots[find(s)] for s in service_ids}


def main() -> None:
    setup_style()
    data = solve_d.load_inputs(ROOT)
    nodes = data["nodes"]
    depot = nodes["O01"]
    service_ids = sorted(k for k in nodes if k.startswith("S"))
    boxes = data["boxes"].copy()
    q1 = pd.read_csv(RESULTS / "q1_batches.csv")
    q2t = pd.read_csv(RESULTS / "q2_transport_trips.csv")
    q2d = pd.read_csv(RESULTS / "q2_box_deliveries.csv")
    q3t = pd.read_csv(RESULTS / "q3_transport_trips.csv")
    q3r = pd.read_csv(RESULTS / "q3_relay_missions.csv")
    q3c = pd.read_csv(RESULTS / "q3_communication_segments.csv")
    q4p = pd.read_csv(RESULTS / "q4_partition_resources.csv")
    q4s = pd.read_csv(RESULTS / "q4_shortage_redundancy.csv")

    # RAW Q1: spatial demand against one-way distance.
    demand = boxes.groupby("服务区编号")["单箱质量（kg）"].sum()
    dist = pd.Series({s: distance_m(depot, nodes[s]) / 1000 for s in service_ids})
    fig, ax = plt.subplots(figsize=(6.3, 4.0))
    sizes = boxes.groupby("服务区编号").size().reindex(service_ids)
    ax.scatter(dist, demand.reindex(service_ids), s=25 + sizes * 10, color=COLORS["blue"],
               alpha=.78, edgecolor="white", linewidth=0.7)
    label_offsets = {"S002": (4, -12), "S003": (4, 6), "S010": (-24, 7), "S013": (5, 7)}
    for s in service_ids:
        ax.annotate(s, (dist[s], demand[s]), xytext=label_offsets.get(s, (3, 3)),
                    textcoords="offset points", fontsize=7)
    ax.set(xlabel="调度中心至服务区直线距离 / km", ylabel="需求总质量 / kg", title="服务区距离与物资需求规模")
    ax.text(.98, .04, "点面积表示货箱数量", transform=ax.transAxes, ha="right", fontsize=8, color=COLORS["gray"])
    fig.tight_layout(); save(fig, "raw_q1_distance_demand")

    # RAW Q2: expected/hard deadlines and priorities.
    fig, ax = plt.subplots(figsize=(6.3, 4.0))
    hard = boxes["首批截止时间（s）"].notna()
    ax.scatter(boxes.loc[~hard, "期望送达时间（s）"] / 3600, boxes.loc[~hard, "应急优先系数"],
               s=22 + boxes.loc[~hard, "单箱质量（kg）"] * 2.2, alpha=0.55, color=COLORS["blue"], label="一般货箱")
    ax.scatter(boxes.loc[hard, "首批截止时间（s）"] / 3600, boxes.loc[hard, "应急优先系数"],
               s=28 + boxes.loc[hard, "单箱质量（kg）"] * 2.2, alpha=0.9, marker="D", color=COLORS["red"], label="首批保障")
    ax.set(xlabel="截止或期望送达时间 / h", ylabel="应急优先系数", title="货箱时限与应急优先级分布")
    ax.legend(frameon=False); fig.tight_layout(); save(fig, "raw_q2_deadline_priority")

    # RAW Q3: mission phase composition.
    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    y = np.arange(len(q3r))
    transit_ready = q3r["link_ready_s"] - q3r["start_s"]
    service = q3r["service_end_s"] - q3r["link_ready_s"]
    recovery = q3r["return_s"] - q3r["service_end_s"]
    ax.barh(y, transit_ready / 60, color=COLORS["blue"], label="准备、飞抵与建链")
    ax.barh(y, service / 60, left=transit_ready / 60, color=COLORS["green"], label="在位保障")
    ax.barh(y, recovery / 60, left=(transit_ready + service) / 60, color=COLORS["orange"], label="返航")
    ax.set_yticks(y, q3r["mission_id"]); ax.invert_yaxis()
    ax.set(xlabel="任务阶段时长 / min", ylabel="中继任务", title="中继架次阶段构成")
    ax.legend(ncol=3, frameon=False, loc="lower right"); fig.tight_layout(); save(fig, "raw_q3_relay_phase_duration")

    # RAW Q4: atomic components caused by multi-stop routes.
    components = union_components(service_ids, q3t["route"].tolist())
    fig, ax = plt.subplots(figsize=(6.3, 4.8))
    palette = plt.get_cmap("tab10")
    for s in service_ids:
        n = nodes[s]
        ax.scatter(n.lon, n.lat, color=palette((components[s] - 1) % 10), s=45, zorder=3)
        ax.text(n.lon + 0.0007, n.lat + 0.0005, s, fontsize=7)
    for route in q3t["route"].astype(str):
        rr = [x for x in route.split(";") if x]
        if len(rr) > 1:
            ax.plot([nodes[x].lon for x in rr], [nodes[x].lat for x in rr], color="#999999", lw=0.9, alpha=0.7)
    ax.scatter(depot.lon, depot.lat, marker="*", s=120, color="black", label="O01")
    ax.set(xlabel="经度 / °E", ylabel="纬度 / °N", title=f"冻结路线诱导的 {len(set(components.values()))} 个原子任务块")
    ax.legend(frameon=False); ax.set_aspect(1 / math.cos(math.radians(np.mean([nodes[s].lat for s in service_ids]))))
    fig.tight_layout(); save(fig, "raw_q4_atomic_components")

    # PROCESS Q1: reserve sensitivity.
    sens1 = pd.read_csv(RESULTS / "sensitivity_q1_reserve.csv")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6.3, 5.2), sharex=True)
    ax1.plot(sens1["reserve"] * 100, sens1["trip_count"], "o-", color=COLORS["blue"])
    ax2.plot(sens1["reserve"] * 100, sens1["energy_kwh"], "s-", color=COLORS["orange"])
    for ax in (ax1, ax2):
        ax.axvline(20, color=COLORS["gray"], ls=":", lw=1)
    ax1.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax1.set(ylabel="最少架次数", title="返航余量敏感性")
    ax2.set(xlabel="返航余量 / %", ylabel="总能耗 / kWh")
    ax1.text(20.5, sens1["trip_count"].min() + 0.08, "基准 20%", fontsize=8)
    fig.tight_layout(); save(fig, "process_q1_reserve_sensitivity")

    # PROCESS Q2: transport UAV Gantt.
    units = sorted(q2t["unit_id"].unique())
    uy = {u: i for i, u in enumerate(units)}
    fig, ax = plt.subplots(figsize=(7.2, 4.5))
    for _, r in q2t.sort_values("start_s").iterrows():
        ax.barh(uy[r.unit_id], (r.return_s - r.start_s) / 3600, left=r.start_s / 3600,
                height=0.58, color=COLORS[{"A": "blue", "B": "orange", "C": "green"}[r.type_id]], alpha=0.85)
    ax.set_yticks(range(len(units)), units); ax.invert_yaxis()
    ax.set(xlabel="时间 / h", ylabel="运输无人机实体", title="问题二运输无人机任务甘特图")
    handles = [mpl.patches.Patch(color=COLORS[c], label=f"{t} 型") for t, c in [("A", "blue"), ("B", "orange"), ("C", "green")]]
    ax.legend(handles=handles, frameon=False, ncol=3); fig.tight_layout(); save(fig, "process_q2_uav_gantt")

    # PROCESS Q3: relay resource Gantt.
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    relay_units = sorted(q3r["relay_unit_id"].unique()); ry = {u: i for i, u in enumerate(relay_units)}
    wave_colors = {w: plt.get_cmap("tab10")(i) for i, w in enumerate(sorted(q3r["wave"].unique()))}
    for _, r in q3r.sort_values("start_s").iterrows():
        ax.barh(ry[r.relay_unit_id], (r.return_s-r.start_s)/3600, left=r.start_s/3600,
                height=.48, color=wave_colors[r.wave], edgecolor="white")
        ax.text((r.start_s+r.return_s)/7200, ry[r.relay_unit_id], r.wave, ha="center", va="center", fontsize=7)
    ax.set_yticks(range(len(relay_units)), relay_units); ax.invert_yaxis()
    ax.set(xlabel="时间 / h", ylabel="中继无人机实体", title="中继波次与实体资源占用")
    fig.tight_layout(); save(fig, "process_q3_relay_gantt")

    # PROCESS Q4: shortage and redundancy by resource.
    resources = q4s["resource"].drop_duplicates().tolist(); y = np.arange(len(resources)); offsets = {2: -0.12, 3: 0.12}
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.2, 4.5), sharey=True)
    for k, marker, color in [(2, "o", COLORS["blue"]), (3, "s", COLORS["orange"])]:
        d = q4s[q4s.K == k].set_index("resource").reindex(resources)
        ax1.scatter(d["shortfall"], y + offsets[k], marker=marker, color=color, label=f"K={k}")
        ax2.scatter(d["partition_redundancy"], y + offsets[k], marker=marker, color=color, label=f"K={k}")
    ax1.set_yticks(y, resources); ax1.invert_yaxis(); ax1.set_xlabel("相对库存缺口 / 件"); ax1.set_title("库存缺口")
    ax2.set_xlabel("相对集中方案冗余 / 件"); ax2.set_title("分区冗余"); ax2.legend(frameon=False)
    fig.suptitle("分区资源代价比较", y=.99); fig.tight_layout(); save(fig, "process_q4_resource_tradeoff")

    # RESULT Q1: mass and volume utilization of every trip.
    capacities_mass = {k: v.payload_kg for k, v in data["transport_types"].items()}
    capacities_vol = {k: v.volume_m3 for k, v in data["transport_types"].items()}
    mass_u = q1.apply(lambda r: r.mass_kg / capacities_mass[r.type_id], axis=1)
    vol_u = q1.apply(lambda r: r.volume_m3 / capacities_vol[r.type_id], axis=1)
    fig, ax = plt.subplots(figsize=(6.0, 4.7))
    util = pd.DataFrame({"type_id": q1.type_id, "mass_u": mass_u * 100, "vol_u": vol_u * 100})
    grouped = util.groupby(["type_id", "mass_u", "vol_u"], as_index=False).size()
    for t, color in [("B", "orange"), ("C", "green")]:
        d = grouped[grouped.type_id == t]
        ax.scatter(d.mass_u, d.vol_u, s=42 + 18*d["size"], color=COLORS[color],
                   label=f"{t} 型", alpha=.82, edgecolor="white", linewidth=.6)
        for _, r in d.iterrows():
            if r["size"] > 1:
                ax.annotate(f"n={int(r['size'])}", (r.mass_u, r.vol_u), xytext=(5, 4),
                            textcoords="offset points", fontsize=7)
    ax.axvline(100, color="#555555", lw=.8, ls=":"); ax.axhline(100, color="#555555", lw=.8, ls=":")
    ax.set(xlabel="质量利用率 / %", ylabel="体积利用率 / %", title="问题一各架次载荷利用率")
    ax.legend(frameon=False); fig.tight_layout(); save(fig, "result_q1_batch_utilization")

    # RESULT Q2: completion time against effective deadline.
    deadline = q2d["hard_deadline_s"].where(q2d["hard_deadline_s"].notna(), q2d["expected_s"])
    hard_mask = q2d["hard_deadline_s"].notna()
    fig, ax = plt.subplots(figsize=(5.8, 5.0))
    ax.scatter(deadline[~hard_mask]/3600, q2d.loc[~hard_mask, "completion_s"]/3600, alpha=.6, color=COLORS["blue"], label="软期望")
    ax.scatter(deadline[hard_mask]/3600, q2d.loc[hard_mask, "completion_s"]/3600, marker="D", color=COLORS["red"], label="硬截止")
    lim = max(deadline.max(), q2d.completion_s.max())/3600 * 1.04
    ax.plot([0, lim], [0, lim], ls="--", lw=1, color="#555555", label="按时边界")
    ax.set(xlim=(0, lim), ylim=(0, lim), xlabel="截止/期望时刻 / h", ylabel="实际完成时刻 / h", title="逐箱完成时刻与时限")
    ax.legend(frameon=False); ax.set_aspect("equal", adjustable="box"); fig.tight_layout(); save(fig, "result_q2_delivery_deadlines")

    # RESULT Q3: communication state timeline and conservative margins.
    trips = sorted(q3c["trip_id"].unique(), key=lambda x: int(str(x)[1:])); ty = {t: i for i, t in enumerate(trips)}
    fig, ax = plt.subplots(figsize=(8.0, 6.0))
    margin_bins = [0, .5, 2, 5, np.inf]
    # Luminance-separated colors remain distinguishable in grayscale preview.
    margin_colors = ["#3B0F70", "#B63679", "#2A9D8F", "#EDC948"]
    margin_labels = ["0–0.5 dB", "0.5–2 dB", "2–5 dB", "≥5 dB"]
    for _, r in q3c.iterrows():
        relay = str(r.phase).startswith("relay")
        bin_id = int(np.digitize([r.margin_lower_db], margin_bins[1:-1], right=False)[0])
        color = margin_colors[bin_id]
        ax.barh(ty[r.trip_id], (r.end_s-r.start_s)/3600, left=r.start_s/3600,
                height=.62, color=color, hatch="///" if relay else None, edgecolor="white", linewidth=.3)
    ax.set_yticks(range(len(trips)), trips); ax.invert_yaxis()
    ax.set(xlabel="时间 / h", ylabel="运输架次", title="全程通信保障时序（斜线为中继链路）")
    handles = [mpl.patches.Patch(color=c, label=lab) for c, lab in zip(margin_colors, margin_labels)]
    handles.append(mpl.patches.Patch(facecolor="white", edgecolor=COLORS["gray"], hatch="///", label="中继链路"))
    ax.legend(handles=handles, ncol=5, frameon=False, loc="upper center",
              bbox_to_anchor=(.5, -0.10), borderaxespad=0)
    fig.tight_layout(rect=(0, .055, 1, 1)); save(fig, "result_q3_communication_timeline")

    # RESULT Q4: selected K=2 and K=3 partitions.
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.4), sharex=True, sharey=True)
    for ax, k in zip(axes, [2, 3]):
        selected = q4p[q4p.K == k]
        groups = {}
        for _, row in selected.iterrows():
            for s in str(row.services).split(";"):
                groups[s] = int(row.group)
        group_markers = {1: "o", 2: "s", 3: "^"}
        for s in service_ids:
            n = nodes[s]; g = groups[s]
            ax.scatter(n.lon, n.lat, s=52, marker=group_markers[g],
                       color=plt.get_cmap("Set2")((g-1)/max(k-1,1)), edgecolor="#444444", linewidth=.45)
            ax.text(n.lon+.0006, n.lat+.0004, s, fontsize=6.5)
        ax.scatter(depot.lon, depot.lat, marker="*", s=110, color="black")
        handles = [mpl.lines.Line2D([], [], marker=group_markers[g], ls="", markersize=6,
                                   color=plt.get_cmap("Set2")((g-1)/max(k-1,1)), label=f"任务组 {g}")
                   for g in range(1, k+1)]
        ax.legend(handles=handles, frameon=False, loc="upper center", ncol=k,
                  bbox_to_anchor=(.5, -0.14), borderaxespad=0)
        ax.set_title(f"K={k} 最优分区"); ax.set_xlabel("经度 / °E")
        ax.set_aspect(1 / math.cos(math.radians(np.mean([nodes[s].lat for s in service_ids]))))
    axes[0].set_ylabel("纬度 / °N")
    fig.suptitle("冻结问题三方案下的任务分区", y=.99); fig.tight_layout(rect=(0, .07, 1, .96)); save(fig, "result_q4_partition_map")

    # Grayscale previews are QA-only and are kept out of the audited figure root.
    qa_dir = FIGURES / "qa"
    qa_dir.mkdir(exist_ok=True)
    for png in FIGURES.glob("*.png"):
        with Image.open(png) as im:
            im.convert("L").save(qa_dir / f"{png.stem}_qa_gray.png", dpi=(300, 300))

    print(f"generated {len(list(FIGURES.glob('*.png')))} PNG and {len(list(FIGURES.glob('*.svg')))} SVG files")


if __name__ == "__main__":
    main()
