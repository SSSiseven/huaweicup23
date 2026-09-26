#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026 华为杯 D 题可复现求解程序。

AI 辅助说明：本程序及代码是在人工智能工具 OpenAI Codex（GPT-5，
开发机构 OpenAI，版本发布日期 2025-08-07）辅助下完成的。
所有模型、参数、约束、输出与引用须由参赛者独立复核后使用。

P1 阶段命令：
    python solve_d.py --mode slice
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import platform
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from PIL import Image


G0 = 9.80665
EARTH_R = 6_371_008.8
SEED = 20_260_923


@dataclass(frozen=True)
class Node:
    node_id: str
    lon: float
    lat: float
    ground_m: float

    @property
    def operation_m(self) -> float:
        return self.ground_m if self.node_id == "O01" else self.ground_m + 30.0


@dataclass(frozen=True)
class TransportType:
    type_id: str
    empty_mass_kg: float
    payload_kg: float
    volume_m3: float
    cruise_mps: float
    empty_range_m: float
    full_range_m: float
    energy_kwh: float
    reserve: float
    prep_s: float
    load_per_box_s: float
    base_handover_s: float
    handover_per_box_s: float
    climb_mps: float
    descent_mps: float
    climb_eff: float


@dataclass(frozen=True)
class RelayType:
    mass_kg: float
    cruise_mps: float
    cruise_kw: float
    energy_kwh: float
    reserve: float
    prep_s: float
    link_s: float
    turnaround_s: float
    climb_mps: float
    descent_mps: float
    climb_eff: float
    hover_kw: float
    comm_kw: float
    max_agl_m: float


class DemGrid:
    """Read-only GeoTIFF DEM reader using Pillow GeoTIFF tags."""

    def __init__(self, path: Path):
        with Image.open(path) as image:
            self.values = np.asarray(image, dtype=float).copy()
            scale = tuple(float(x) for x in image.tag_v2[33550])
            tie = tuple(float(x) for x in image.tag_v2[33922])
        self.dx = scale[0]
        self.dy = scale[1]
        self.lon0 = tie[3]
        self.lat0 = tie[4]
        self.height, self.width = self.values.shape

    def row_col(self, lon: float, lat: float) -> tuple[int, int]:
        col = int(round((lon - self.lon0) / self.dx))
        row = int(round((self.lat0 - lat) / self.dy))
        return row, col

    def inside(self, lon: float, lat: float) -> bool:
        row, col = self.row_col(lon, lat)
        return 0 <= row < self.height and 0 <= col < self.width

    def elevation(self, lon: float, lat: float) -> float:
        row, col = self.row_col(lon, lat)
        row = min(max(row, 0), self.height - 1)
        col = min(max(col, 0), self.width - 1)
        return float(self.values[row, col])

    def path_elevations(
        self, lon1: float, lat1: float, lon2: float, lat2: float, step_m: float = 15.0
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        dist = horizontal_distance_m(lon1, lat1, lon2, lat2)
        count = max(3, int(math.ceil(dist / step_m)) + 1)
        frac = np.linspace(0.0, 1.0, count)
        lons = lon1 + frac * (lon2 - lon1)
        lats = lat1 + frac * (lat2 - lat1)
        cols = np.rint((lons - self.lon0) / self.dx).astype(int)
        rows = np.rint((self.lat0 - lats) / self.dy).astype(int)
        rows = np.clip(rows, 0, self.height - 1)
        cols = np.clip(cols, 0, self.width - 1)
        return frac, self.values[rows, cols], np.column_stack([lons, lats])


def horizontal_distance_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    mean_lat = math.radians((lat1 + lat2) / 2.0)
    dx = EARTH_R * math.cos(mean_lat) * math.radians(lon2 - lon1)
    dy = EARTH_R * math.radians(lat2 - lat1)
    return math.hypot(dx, dy)


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    dp = p2 - p1
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2.0 * EARTH_R * math.asin(math.sqrt(a))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_inputs(project_root: Path) -> dict[str, Any]:
    data_root = project_root / "D题" / "数据" / "无人机应急物资运输基础数据"
    spatial_root = project_root / "D题" / "数据" / "镇龙乡地理空间数据" / "镇龙乡及周边地理数据"
    node_path = data_root / "调度中心与服务区.xlsx"
    demand_path = data_root / "物资需求与配送时限.xlsx"
    transport_path = data_root / "运输无人机数据.xlsx"
    relay_path = data_root / "中继无人机数据.xlsx"
    comm_path = data_root / "通信链路参数.xlsx"
    dem_path = spatial_root / "数字高程模型数据（DEM）" / "镇龙乡及周边30米DEM.tif"

    node_raw = pd.read_excel(node_path, sheet_name="数据", header=None)
    nodes: dict[str, Node] = {}
    depot_row = node_raw.iloc[2]
    nodes[str(depot_row.iloc[0])] = Node(
        str(depot_row.iloc[0]), float(depot_row.iloc[2]), float(depot_row.iloc[3]), float(depot_row.iloc[4])
    )
    for _, row in node_raw.iloc[6:21].iterrows():
        nodes[str(row.iloc[0])] = Node(
            str(row.iloc[0]), float(row.iloc[2]), float(row.iloc[3]), float(row.iloc[4])
        )

    boxes = pd.read_excel(demand_path, sheet_name="逐箱货箱清单", header=0)
    if len(boxes) != 80 or boxes["货箱编号"].nunique() != 80:
        raise ValueError(f"逐箱表应为80个唯一货箱，实际行数={len(boxes)}，唯一数={boxes['货箱编号'].nunique()}")
    summary = pd.read_excel(demand_path, sheet_name="数据", header=0)
    if len(summary) != 53:
        raise ValueError(f"需求汇总应为53条数据记录，实际={len(summary)}")

    transport_raw = pd.read_excel(transport_path, sheet_name="数据", header=None)
    transport_types: dict[str, TransportType] = {}
    for _, row in transport_raw.iloc[2:5].iterrows():
        g = str(row.iloc[0])
        transport_types[g] = TransportType(
            type_id=g,
            empty_mass_kg=float(row.iloc[2]),
            payload_kg=float(row.iloc[3]),
            volume_m3=float(row.iloc[4]),
            cruise_mps=float(row.iloc[5]),
            empty_range_m=float(row.iloc[6]),
            full_range_m=float(row.iloc[7]),
            energy_kwh=float(row.iloc[8]),
            reserve=float(row.iloc[9]) / 100.0,
            prep_s=float(row.iloc[10]),
            load_per_box_s=float(row.iloc[11]),
            base_handover_s=float(row.iloc[12]),
            handover_per_box_s=float(row.iloc[13]),
            climb_mps=float(row.iloc[14]),
            descent_mps=float(row.iloc[15]),
            climb_eff=float(row.iloc[16]),
        )
    transport_units = [
        {"unit_id": str(row.iloc[0]), "type_id": str(row.iloc[1])}
        for _, row in transport_raw.iloc[8:16].iterrows()
    ]
    battery_inventory = {
        str(row.iloc[0]): {"count": int(row.iloc[1]), "full_charge_s": float(row.iloc[2])}
        for _, row in transport_raw.iloc[19:22].iterrows()
    }

    relay_raw = pd.read_excel(relay_path, sheet_name="数据", header=None)
    rr = relay_raw.iloc[2]
    relay_type = RelayType(
        mass_kg=float(rr.iloc[4]),
        cruise_mps=float(rr.iloc[5]),
        cruise_kw=float(rr.iloc[6]),
        energy_kwh=float(rr.iloc[7]),
        reserve=float(rr.iloc[8]) / 100.0,
        prep_s=float(rr.iloc[9]),
        link_s=float(rr.iloc[10]),
        turnaround_s=float(rr.iloc[11]),
        climb_mps=float(rr.iloc[12]),
        descent_mps=float(rr.iloc[13]),
        climb_eff=float(rr.iloc[14]),
        hover_kw=float(rr.iloc[16]),
        comm_kw=float(rr.iloc[17]),
        max_agl_m=float(rr.iloc[18]),
    )
    relay_inventory = {
        "units": int(relay_raw.iloc[6:8, 0].notna().sum()),
        "packs": int(relay_raw.iloc[11, 1]),
        "full_charge_s": float(relay_raw.iloc[11, 2]),
    }

    comm_raw = pd.read_excel(comm_path, sheet_name="数据", header=None)
    comm = {str(row.iloc[1]): float(row.iloc[4]) for _, row in comm_raw.iloc[2:16].iterrows()}
    # Directional endpoint parameters from fixed row positions.
    endpoints = {
        "transport": {"pt": float(comm_raw.iloc[7, 4]), "gain": float(comm_raw.iloc[8, 4])},
        "relay_access": {"pt": float(comm_raw.iloc[9, 4]), "gain": float(comm_raw.iloc[10, 4])},
        "relay_backhaul": {"pt": float(comm_raw.iloc[11, 4]), "gain": float(comm_raw.iloc[12, 4])},
        "gateway": {"pt": float(comm_raw.iloc[13, 4]), "gain": float(comm_raw.iloc[14, 4])},
    }
    pth = comm["接收灵敏度（dBm）"] + comm["衰落裕量（dB）"]
    lsys = comm["系统损耗（dB）"]

    def bidir(a: str, b: str) -> float:
        ab = endpoints[a]["pt"] + endpoints[a]["gain"] + endpoints[b]["gain"] - lsys - pth
        ba = endpoints[b]["pt"] + endpoints[b]["gain"] + endpoints[a]["gain"] - lsys - pth
        return min(ab, ba)

    thresholds = {
        "transport_gateway": bidir("transport", "gateway"),
        "transport_relay": bidir("transport", "relay_access"),
        "relay_gateway": bidir("relay_backhaul", "gateway"),
    }

    input_paths = [node_path, demand_path, transport_path, relay_path, comm_path, dem_path]
    return {
        "nodes": nodes,
        "boxes": boxes,
        "summary": summary,
        "transport_types": transport_types,
        "transport_units": transport_units,
        "battery_inventory": battery_inventory,
        "relay_type": relay_type,
        "relay_inventory": relay_inventory,
        "comm": comm,
        "thresholds": thresholds,
        "dem": DemGrid(dem_path),
        "input_hashes": {str(path.relative_to(project_root)): sha256(path) for path in input_paths},
    }


def equivalent_range_m(g: TransportType, payload_kg: float) -> float:
    ratio = min(max(payload_kg / g.payload_kg, 0.0), 1.0)
    return g.empty_range_m - (g.empty_range_m - g.full_range_m) * ratio ** 1.5


def leg_metrics(dem: DemGrid, a: Node, b: Node, g: TransportType, payload_kg: float) -> dict[str, float]:
    distance = horizontal_distance_m(a.lon, a.lat, b.lon, b.lat)
    _, elev, _ = dem.path_elevations(a.lon, a.lat, b.lon, b.lat)
    cruise = float(np.max(elev) + 50.0)
    climb = max(0.0, cruise - a.operation_m)
    descent = max(0.0, cruise - b.operation_m)
    flight_s = climb / g.climb_mps + distance / g.cruise_mps + descent / g.descent_mps
    horizontal_kwh = g.energy_kwh * distance / equivalent_range_m(g, payload_kg)
    climb_kwh = (g.empty_mass_kg + payload_kg) * G0 * climb / (3.6e6 * g.climb_eff)
    return {
        "distance_m": distance,
        "cruise_alt_m": cruise,
        "climb_m": climb,
        "descent_m": descent,
        "time_s": flight_s,
        "energy_kwh": horizontal_kwh + climb_kwh,
    }


def direct_round_trip(dem: DemGrid, depot: Node, service: Node, g: TransportType, payload_kg: float) -> dict[str, float]:
    outbound = leg_metrics(dem, depot, service, g, payload_kg)
    inbound = leg_metrics(dem, service, depot, g, 0.0)
    energy = outbound["energy_kwh"] + inbound["energy_kwh"]
    return {
        "energy_kwh": energy,
        "flight_s": outbound["time_s"] + inbound["time_s"],
        "return_soc": 1.0 - energy / g.energy_kwh,
        "outbound_s": outbound["time_s"],
        "inbound_s": inbound["time_s"],
        "outbound_cruise_m": outbound["cruise_alt_m"],
        "inbound_cruise_m": inbound["cruise_alt_m"],
    }


def max_safe_payload(dem: DemGrid, depot: Node, service: Node, g: TransportType) -> float:
    limit = (1.0 - g.reserve) * g.energy_kwh
    if direct_round_trip(dem, depot, service, g, g.payload_kg)["energy_kwh"] <= limit:
        return g.payload_kg
    lo, hi = 0.0, g.payload_kg
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if direct_round_trip(dem, depot, service, g, mid)["energy_kwh"] <= limit:
            lo = mid
        else:
            hi = mid
    return lo


def box_deadline(row: pd.Series) -> float | None:
    values: list[float] = []
    if str(row["物资类型"]) == "医疗物资" and pd.notna(row["期望送达时间（s）"]):
        values.append(float(row["期望送达时间（s）"]))
    if str(row["是否首批保障"]) == "是" and pd.notna(row["首批截止时间（s）"]):
        values.append(float(row["首批截止时间（s）"]))
    return min(values) if values else None


def batch_metrics(
    dem: DemGrid, depot: Node, service: Node, g: TransportType, batch: pd.DataFrame
) -> dict[str, float]:
    mass = float(batch["单箱质量（kg）"].sum())
    volume = float(batch["单箱体积（m³）"].sum())
    trip = direct_round_trip(dem, depot, service, g, mass)
    duration = (
        g.prep_s
        + len(batch) * g.load_per_box_s
        + trip["flight_s"]
        + g.base_handover_s
        + len(batch) * g.handover_per_box_s
    )
    return {**trip, "mass_kg": mass, "volume_m3": volume, "duration_s": duration}


def exact_q1_service(
    dem: DemGrid,
    depot: Node,
    service: Node,
    boxes: pd.DataFrame,
    types: dict[str, TransportType],
) -> list[dict[str, Any]]:
    boxes = boxes.reset_index(drop=True)
    n = len(boxes)
    full = (1 << n) - 1
    candidates: dict[int, list[dict[str, Any]]] = {}
    for mask in range(1, full + 1):
        idx = [i for i in range(n) if mask & (1 << i)]
        batch = boxes.iloc[idx]
        for type_id, g in types.items():
            metrics = batch_metrics(dem, depot, service, g, batch)
            feasible = (
                metrics["mass_kg"] <= g.payload_kg + 1e-9
                and metrics["volume_m3"] <= g.volume_m3 + 1e-12
                and metrics["energy_kwh"] <= (1.0 - g.reserve) * g.energy_kwh + 1e-9
            )
            if feasible:
                candidates.setdefault(mask, []).append(
                    {
                        "mask": mask,
                        "type_id": type_id,
                        "box_ids": list(batch["货箱编号"].astype(str)),
                        **metrics,
                    }
                )
    dp: dict[int, tuple[tuple[float, float, float], list[dict[str, Any]]]] = {0: ((0, 0.0, 0.0), [])}
    for covered in range(full + 1):
        if covered not in dp:
            continue
        remaining = full ^ covered
        if remaining == 0:
            continue
        first_bit = remaining & -remaining
        for mask, options in candidates.items():
            if not (mask & first_bit) or (mask & covered):
                continue
            for cand in options:
                old_cost, old_path = dp[covered]
                new_cost = (
                    old_cost[0] + 1,
                    old_cost[1] + cand["energy_kwh"],
                    old_cost[2] + cand["duration_s"],
                )
                new_mask = covered | mask
                if new_mask not in dp or new_cost < dp[new_mask][0]:
                    dp[new_mask] = (new_cost, old_path + [cand])
    if full not in dp:
        raise RuntimeError(f"Q1 service {service.node_id} has no feasible partition")
    return dp[full][1]


def single_service_timeline(
    dem: DemGrid,
    depot: Node,
    service: Node,
    g: TransportType,
    batch: pd.DataFrame,
    start_s: float,
) -> dict[str, Any]:
    batch = batch.copy()
    batch["hard_deadline_s"] = batch.apply(box_deadline, axis=1)
    batch["sort_deadline"] = batch["hard_deadline_s"].fillna(np.inf)
    batch = batch.sort_values(
        ["sort_deadline", "应急优先系数", "货箱编号"], ascending=[True, False, True]
    )
    payload = float(batch["单箱质量（kg）"].sum())
    metrics = direct_round_trip(dem, depot, service, g, payload)
    takeoff = start_s + g.prep_s + len(batch) * g.load_per_box_s
    arrival = takeoff + metrics["outbound_s"]
    completions: list[dict[str, Any]] = []
    for order, (_, row) in enumerate(batch.iterrows(), start=1):
        completion = arrival + g.base_handover_s + order * g.handover_per_box_s
        deadline = box_deadline(row)
        completions.append(
            {
                "box_id": str(row["货箱编号"]),
                "service_id": service.node_id,
                "completion_s": completion,
                "hard_deadline_s": deadline,
                "hard_on_time": deadline is None or completion <= deadline + 1e-9,
            }
        )
    depart = arrival + g.base_handover_s + len(batch) * g.handover_per_box_s
    returned = depart + metrics["inbound_s"]
    return {
        "start_s": start_s,
        "takeoff_s": takeoff,
        "arrival_s": arrival,
        "depart_service_s": depart,
        "return_s": returned,
        "payload_kg": payload,
        "energy_kwh": metrics["energy_kwh"],
        "return_soc": metrics["return_soc"],
        "outbound_cruise_m": metrics["outbound_cruise_m"],
        "inbound_cruise_m": metrics["inbound_cruise_m"],
        "completions": completions,
    }


def fspl_db(freq_mhz: float, distance_km: float) -> float:
    return 32.45 + 20.0 * math.log10(freq_mhz) + 20.0 * math.log10(max(distance_km, 1e-9))


def link_state(
    dem: DemGrid,
    a: tuple[float, float, float],
    b: tuple[float, float, float],
    threshold_db: float,
    freq_mhz: float,
    obstruction_db: float,
) -> dict[str, Any]:
    lon1, lat1, alt1 = a
    lon2, lat2, alt2 = b
    horizontal = horizontal_distance_m(lon1, lat1, lon2, lat2)
    frac, terrain, _ = dem.path_elevations(lon1, lat1, lon2, lat2, step_m=15.0)
    sight = alt1 + frac * (alt2 - alt1)
    if len(frac) > 2:
        clearance = sight[1:-1] - terrain[1:-1]
        min_clearance = float(np.min(clearance))
        blocked = bool(np.any(clearance <= 0.0))
    else:
        min_clearance = float("inf")
        blocked = False
    distance_3d_km = math.hypot(horizontal, alt2 - alt1) / 1000.0
    loss = fspl_db(freq_mhz, distance_3d_km) + (obstruction_db if blocked else 0.0)
    return {
        "available": bool(loss <= threshold_db + 1e-12),
        "blocked": blocked,
        "loss_db": loss,
        "margin_db": threshold_db - loss,
        "min_clearance_m": min_clearance,
        "distance_3d_km": distance_3d_km,
    }


def transport_trajectory(
    dem: DemGrid,
    depot: Node,
    service: Node,
    g: TransportType,
    timeline: dict[str, Any],
) -> list[dict[str, Any]]:
    """Piecewise-linear 3-D trajectory from takeoff through return."""

    out = leg_metrics(dem, depot, service, g, timeline["payload_kg"])
    back = leg_metrics(dem, service, depot, g, 0.0)
    phases: list[dict[str, Any]] = []

    def append_leg(start_t: float, a: Node, b: Node, leg: dict[str, float], prefix: str) -> float:
        t1 = start_t + leg["climb_m"] / g.climb_mps
        t2 = t1 + leg["distance_m"] / g.cruise_mps
        t3 = t2 + leg["descent_m"] / g.descent_mps
        phases.extend(
            [
                {
                    "name": f"{prefix}_climb",
                    "t0": start_t,
                    "t1": t1,
                    "p0": (a.lon, a.lat, a.operation_m),
                    "p1": (a.lon, a.lat, leg["cruise_alt_m"]),
                },
                {
                    "name": f"{prefix}_cruise",
                    "t0": t1,
                    "t1": t2,
                    "p0": (a.lon, a.lat, leg["cruise_alt_m"]),
                    "p1": (b.lon, b.lat, leg["cruise_alt_m"]),
                },
                {
                    "name": f"{prefix}_descent",
                    "t0": t2,
                    "t1": t3,
                    "p0": (b.lon, b.lat, leg["cruise_alt_m"]),
                    "p1": (b.lon, b.lat, b.operation_m),
                },
            ]
        )
        return t3

    arrival = append_leg(timeline["takeoff_s"], depot, service, out, "outbound")
    phases.append(
        {
            "name": "handover",
            "t0": arrival,
            "t1": timeline["depart_service_s"],
            "p0": (service.lon, service.lat, service.operation_m),
            "p1": (service.lon, service.lat, service.operation_m),
        }
    )
    append_leg(timeline["depart_service_s"], service, depot, back, "return")
    return [p for p in phases if p["t1"] > p["t0"] + 1e-9]


def position_at(phases: list[dict[str, Any]], t: float) -> tuple[float, float, float]:
    for phase in phases:
        if phase["t0"] - 1e-9 <= t <= phase["t1"] + 1e-9:
            frac = 0.0 if phase["t1"] == phase["t0"] else (t - phase["t0"]) / (phase["t1"] - phase["t0"])
            return tuple(float(a + frac * (b - a)) for a, b in zip(phase["p0"], phase["p1"]))
    raise ValueError(f"time {t} outside trajectory")


def relay_flight_metrics(
    dem: DemGrid, depot: Node, relay: RelayType, lon: float, lat: float, altitude_m: float, service_s: float
) -> dict[str, float]:
    distance = horizontal_distance_m(depot.lon, depot.lat, lon, lat)
    _, elev, _ = dem.path_elevations(depot.lon, depot.lat, lon, lat)
    cruise_alt = max(float(np.max(elev) + 50.0), altitude_m)
    out_up = max(0.0, cruise_alt - depot.operation_m)
    out_down = max(0.0, cruise_alt - altitude_m)
    back_up = max(0.0, cruise_alt - altitude_m)
    back_down = max(0.0, cruise_alt - depot.operation_m)
    out_s = out_up / relay.climb_mps + distance / relay.cruise_mps + out_down / relay.descent_mps
    back_s = back_up / relay.climb_mps + distance / relay.cruise_mps + back_down / relay.descent_mps
    cruise_energy = relay.cruise_kw * (2.0 * distance / relay.cruise_mps) / 3600.0
    climb_energy = relay.mass_kg * G0 * (out_up + back_up) / (3.6e6 * relay.climb_eff)
    hover_energy = (relay.hover_kw + relay.comm_kw) * (relay.link_s + service_s) / 3600.0
    energy = cruise_energy + climb_energy + hover_energy
    return {
        "distance_m": distance,
        "cruise_alt_m": cruise_alt,
        "outbound_s": out_s,
        "return_s": back_s,
        "link_ready_offset_s": relay.prep_s + out_s + relay.link_s,
        "energy_kwh": energy,
        "return_soc": 1.0 - energy / relay.energy_kwh,
        "feasible_energy": energy <= (1.0 - relay.reserve) * relay.energy_kwh + 1e-9,
    }


def _local_xy_m(lon: float, lat: float, ref_lon: float, ref_lat: float) -> tuple[float, float]:
    # Fixed-reference equirectangular projection.  The constant x scale makes
    # straight lon/lat interpolation affine in this local plane, which is needed
    # by the swept-triangle altitude certificate below.
    mean_lat = math.radians(ref_lat)
    return (
        EARTH_R * math.cos(mean_lat) * math.radians(lon - ref_lon),
        EARTH_R * math.radians(lat - ref_lat),
    )


def _point_segment_distance_m(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> tuple[float, float]:
    vx, vy = bx - ax, by - ay
    denom = vx * vx + vy * vy
    if denom <= 1e-18:
        return math.hypot(px - ax, py - ay), 0.0
    r = min(1.0, max(0.0, ((px - ax) * vx + (py - ay) * vy) / denom))
    qx, qy = ax + r * vx, ay + r * vy
    return math.hypot(px - qx, py - qy), r


def _clip_polygon_rect(
    polygon: list[tuple[float, float]], xmin: float, xmax: float, ymin: float, ymax: float
) -> list[tuple[float, float]]:
    """Sutherland-Hodgman clipping against an axis-aligned rectangle."""

    def clip(
        points: list[tuple[float, float]], inside: Any, intersect: Any
    ) -> list[tuple[float, float]]:
        if not points:
            return []
        output: list[tuple[float, float]] = []
        previous = points[-1]
        previous_inside = inside(previous)
        for current in points:
            current_inside = inside(current)
            if current_inside != previous_inside:
                output.append(intersect(previous, current))
            if current_inside:
                output.append(current)
            previous, previous_inside = current, current_inside
        return output

    def vertical(a: tuple[float, float], b: tuple[float, float], x: float) -> tuple[float, float]:
        ratio = (x - a[0]) / (b[0] - a[0])
        return x, a[1] + ratio * (b[1] - a[1])

    def horizontal(a: tuple[float, float], b: tuple[float, float], y: float) -> tuple[float, float]:
        ratio = (y - a[1]) / (b[1] - a[1])
        return a[0] + ratio * (b[0] - a[0]), y

    out = polygon
    out = clip(out, lambda p: p[0] >= xmin, lambda a, b: vertical(a, b, xmin))
    out = clip(out, lambda p: p[0] <= xmax, lambda a, b: vertical(a, b, xmax))
    out = clip(out, lambda p: p[1] >= ymin, lambda a, b: horizontal(a, b, ymin))
    out = clip(out, lambda p: p[1] <= ymax, lambda a, b: horizontal(a, b, ymax))
    return out


def _polygon_area(polygon: list[tuple[float, float]]) -> float:
    if len(polygon) < 3:
        return 0.0
    return 0.5 * abs(
        sum(
            polygon[i][0] * polygon[(i + 1) % len(polygon)][1]
            - polygon[(i + 1) % len(polygon)][0] * polygon[i][1]
            for i in range(len(polygon))
        )
    )


def _segment_rect_parameter_interval(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    xmin: float,
    xmax: float,
    ymin: float,
    ymax: float,
) -> tuple[float, float] | None:
    """Liang-Barsky interval of segment parameters lying inside a rectangle."""

    dx, dy = x1 - x0, y1 - y0
    lo, hi = 0.0, 1.0
    for p, q in ((-dx, x0 - xmin), (dx, xmax - x0), (-dy, y0 - ymin), (dy, ymax - y0)):
        if abs(p) <= 1e-18:
            if q < 0.0:
                return None
            continue
        ratio = q / p
        if p < 0.0:
            lo = max(lo, ratio)
        else:
            hi = min(hi, ratio)
        if lo > hi:
            return None
    return lo, hi


def interval_link_certificate(
    dem: DemGrid,
    moving0: tuple[float, float, float],
    moving1: tuple[float, float, float],
    fixed: tuple[float, float, float],
    threshold_db: float,
    freq_mhz: float,
    obstruction_db: float,
) -> dict[str, Any]:
    """Conservative availability certificate over one linear-motion interval.

    The moving endpoint follows the straight segment moving0->moving1.  In plan view,
    every instantaneous radio ray lies inside a narrow swept wedge around the ray to
    the midpoint endpoint.  DEM cells whose rectangles can intersect that wedge are
    conservatively collected using a cell-center distance bound.  For every collected
    cell, a conservative ray-parameter interval gives a lower bound on line altitude.
    This matches the nearest-cell, piecewise-constant DEM model used elsewhere.
    """

    lon_f, lat_f, alt_f = fixed
    p_mid = tuple((a + b) / 2.0 for a, b in zip(moving0, moving1))
    x0, y0 = _local_xy_m(moving0[0], moving0[1], lon_f, lat_f)
    x1, y1 = _local_xy_m(moving1[0], moving1[1], lon_f, lat_f)
    xm, ym = _local_xy_m(p_mid[0], p_mid[1], lon_f, lat_f)
    endpoint_shift = math.hypot(x1 - x0, y1 - y0)
    pixel_x = EARTH_R * math.cos(math.radians(lat_f)) * math.radians(dem.dx)
    pixel_y = EARTH_R * math.radians(dem.dy)
    half_diag = 0.5 * math.hypot(pixel_x, pixel_y)
    sweep_radius = half_diag + endpoint_shift / 2.0 + 1e-6

    # Candidate cells are selected in one vectorized pass over a conservative raster
    # bounding box.  The half-cell diagonal and endpoint motion dilate the midpoint
    # ray into a swept wedge, so no nearest-neighbour DEM cell can be missed.
    length_mid = math.hypot(xm, ym)
    lon_pad = math.degrees(sweep_radius / max(EARTH_R * math.cos(math.radians(lat_f)), 1.0))
    lat_pad = math.degrees(sweep_radius / EARTH_R)
    lon_lo, lon_hi = min(lon_f, p_mid[0]) - lon_pad, max(lon_f, p_mid[0]) + lon_pad
    lat_lo, lat_hi = min(lat_f, p_mid[1]) - lat_pad, max(lat_f, p_mid[1]) + lat_pad
    ra, ca = dem.row_col(lon_lo, lat_hi)
    rb, cb = dem.row_col(lon_hi, lat_lo)
    row_lo, row_hi = max(0, min(ra, rb) - 1), min(dem.height - 1, max(ra, rb) + 1)
    col_lo, col_hi = max(0, min(ca, cb) - 1), min(dem.width - 1, max(ca, cb) + 1)
    row_grid, col_grid = np.meshgrid(
        np.arange(row_lo, row_hi + 1), np.arange(col_lo, col_hi + 1), indexing="ij"
    )
    cell_lons = dem.lon0 + col_grid * dem.dx
    cell_lats = dem.lat0 - row_grid * dem.dy
    cell_x = EARTH_R * math.cos(math.radians(lat_f)) * np.radians(cell_lons - lon_f)
    cell_y = EARTH_R * np.radians(cell_lats - lat_f)
    denom = max(length_mid * length_mid, 1e-18)
    r_center_all = np.clip((cell_x * xm + cell_y * ym) / denom, 0.0, 1.0)
    qx, qy = r_center_all * xm, r_center_all * ym
    dist_all = np.hypot(cell_x - qx, cell_y - qy)
    # 0.5 m absorbs the local equirectangular vectorisation approximation.
    mask = dist_all <= sweep_radius + 0.5
    candidate_rows = row_grid[mask]
    candidate_cols = col_grid[mask]
    candidate_r = r_center_all[mask]

    los_certified = True
    min_clearance_lb = float("inf")
    plan_lengths = [math.hypot(x0, y0), math.hypot(x1, y1)]
    length_floor = max(1e-9, min(plan_lengths))
    r_expand = min(1.0, sweep_radius / length_floor)
    triangle_det = x0 * y1 - x1 * y0
    static_plan = endpoint_shift <= 1e-6
    if candidate_rows.size and abs(triangle_det) > 1e-3:
        # The union of all instantaneous rays is exactly triangle F-M0-M1.
        # Since both plan position and altitude are affine in time, radio-ray
        # altitude is an affine plane over this triangle.  Clip every DEM cell
        # rectangle against the triangle and test the plane only on the clipped
        # polygon vertices, where its minimum must occur.
        plane = np.linalg.solve(
            np.asarray([[0.0, 0.0, 1.0], [x0, y0, 1.0], [x1, y1, 1.0]]),
            np.asarray([alt_f, moving0[2], moving1[2]], dtype=float),
        )
        triangle = [(lon_f, lat_f), (moving0[0], moving0[1]), (moving1[0], moving1[1])]
        clearances: list[float] = []
        for row, col in zip(candidate_rows.tolist(), candidate_cols.tolist()):
            center_lon = dem.lon0 + col * dem.dx
            center_lat = dem.lat0 - row * dem.dy
            clipped = _clip_polygon_rect(
                triangle,
                center_lon - dem.dx / 2.0,
                center_lon + dem.dx / 2.0,
                center_lat - dem.dy / 2.0,
                center_lat + dem.dy / 2.0,
            )
            # Zero-area boundary touches do not occupy a nearest-neighbour cell.
            if _polygon_area(clipped) <= 1e-18:
                continue
            local_vertices = [_local_xy_m(lon, lat, lon_f, lat_f) for lon, lat in clipped]
            altitude_lb = min(plane[0] * x + plane[1] * y + plane[2] for x, y in local_vertices)
            clearances.append(altitude_lb - float(dem.values[row, col]))
        if clearances:
            min_clearance_lb = min(clearances)
            los_certified = bool(min_clearance_lb > 0.0)
    elif candidate_rows.size and static_plan:
        # Vertical transport motion: the plan ray is fixed.  The lower of the two
        # endpoint altitudes gives the exact worst-case line altitude for all times.
        moving_alt = min(moving0[2], moving1[2])
        slope = moving_alt - alt_f
        clearances = []
        for row, col in zip(candidate_rows.tolist(), candidate_cols.tolist()):
            center_lon = dem.lon0 + col * dem.dx
            center_lat = dem.lat0 - row * dem.dy
            interval = _segment_rect_parameter_interval(
                lon_f,
                lat_f,
                moving0[0],
                moving0[1],
                center_lon - dem.dx / 2.0,
                center_lon + dem.dx / 2.0,
                center_lat - dem.dy / 2.0,
                center_lat + dem.dy / 2.0,
            )
            if interval is None or interval[1] - interval[0] <= 1e-12:
                continue
            ray_parameter = interval[0] if slope >= 0.0 else interval[1]
            altitude_lb = alt_f + ray_parameter * slope
            clearances.append(altitude_lb - float(dem.values[row, col]))
        if clearances:
            min_clearance_lb = min(clearances)
            los_certified = bool(min_clearance_lb > 0.0)
    elif candidate_rows.size:
        # Rare collinear plan motion.  Retain the earlier conservative envelope;
        # failure merely triggers subdivision or the alternative relay path.
        r_lo = np.clip(candidate_r - r_expand, 0.0, 1.0)
        r_hi = np.clip(candidate_r + r_expand, 0.0, 1.0)
        slopes = np.asarray([moving0[2] - alt_f, moving1[2] - alt_f], dtype=float)
        altitude_candidates = np.stack(
            [alt_f + r_lo * slopes[0], alt_f + r_hi * slopes[0],
             alt_f + r_lo * slopes[1], alt_f + r_hi * slopes[1]],
            axis=0,
        )
        altitude_lb = np.min(altitude_candidates, axis=0)
        clearance_lb = altitude_lb - dem.values[candidate_rows, candidate_cols]
        min_clearance_lb = float(np.min(clearance_lb))
        los_certified = bool(np.all(clearance_lb > 0.0))

    def distance_3d_km(point: tuple[float, float, float]) -> float:
        h = horizontal_distance_m(point[0], point[1], lon_f, lat_f)
        return math.hypot(h, point[2] - alt_f) / 1000.0

    # Norm of an affine vector is convex, so its maximum over a closed interval is at
    # an endpoint. This makes the distance and FSPL upper bound exact for the interval.
    max_distance_km = max(distance_3d_km(moving0), distance_3d_km(moving1))
    loss_upper = fspl_db(freq_mhz, max_distance_km)
    if not los_certified:
        loss_upper += obstruction_db
    margin_lower = threshold_db - loss_upper
    return {
        "certified_available": bool(margin_lower >= -1e-12),
        "los_certified": los_certified,
        "loss_upper_db": loss_upper,
        "margin_lower_db": margin_lower,
        "min_clearance_lower_m": min_clearance_lb,
        "candidate_cells": int(candidate_rows.size),
        "endpoint_shift_m": endpoint_shift,
        "max_distance_km": max_distance_km,
    }


def find_static_relay(
    dem: DemGrid,
    depot: Node,
    relay: RelayType,
    phases: list[dict[str, Any]],
    comm: dict[str, float],
    thresholds: dict[str, float],
) -> dict[str, Any]:
    gateway = (depot.lon, depot.lat, depot.ground_m + comm["天线离地高度（m）"])
    freq = comm["载波频率（MHz）"]
    obs = comm["地形遮挡附加损耗（dB）"]
    start = phases[0]["t0"]
    end = phases[-1]["t1"]
    sample_times = np.arange(start, end + 1e-9, 2.0)
    if sample_times[-1] < end:
        sample_times = np.append(sample_times, end)
    positions = [position_at(phases, float(t)) for t in sample_times]
    direct = [
        link_state(dem, p, gateway, thresholds["transport_gateway"], freq, obs)["available"]
        for p in positions
    ]
    blackout_positions = [p for p, ok in zip(positions, direct) if not ok]
    if not blackout_positions:
        return {"needed": False, "coverage_fraction": 1.0, "blackout_samples": 0}

    lons = [p[0] for p in blackout_positions] + [depot.lon]
    lats = [p[1] for p in blackout_positions] + [depot.lat]
    lon_min, lon_max = min(lons) - 0.025, max(lons) + 0.025
    lat_min, lat_max = min(lats) - 0.025, max(lats) + 0.025
    r0, c0 = dem.row_col(lon_min, lat_max)
    r1, c1 = dem.row_col(lon_max, lat_min)
    r0, r1 = max(0, min(r0, r1)), min(dem.height - 1, max(r0, r1))
    c0, c1 = max(0, min(c0, c1)), min(dem.width - 1, max(c0, c1))

    best: dict[str, Any] | None = None
    for row in range(r0, r1 + 1, 18):
        for col in range(c0, c1 + 1, 18):
            lon = dem.lon0 + col * dem.dx
            lat = dem.lat0 - row * dem.dy
            ground = float(dem.values[row, col])
            for agl in (150.0, 225.0, relay.max_agl_m):
                point = (lon, lat, ground + agl)
                backhaul = link_state(dem, point, gateway, thresholds["relay_gateway"], freq, obs)
                if not backhaul["available"]:
                    continue
                access_ok = 0
                min_margin = backhaul["margin_db"]
                for p in blackout_positions:
                    state = link_state(dem, p, point, thresholds["transport_relay"], freq, obs)
                    access_ok += int(state["available"])
                    min_margin = min(min_margin, state["margin_db"])
                coverage = access_ok / len(blackout_positions)
                metrics = relay_flight_metrics(dem, depot, relay, lon, lat, point[2], end - start)
                if not metrics["feasible_energy"]:
                    continue
                score = (-coverage, metrics["energy_kwh"], -min_margin, lon, lat, agl)
                candidate = {
                    "needed": True,
                    "lon": lon,
                    "lat": lat,
                    "ground_m": ground,
                    "agl_m": agl,
                    "altitude_m": point[2],
                    "coverage_fraction": coverage,
                    "blackout_samples": len(blackout_positions),
                    "min_link_margin_db": min_margin,
                    "backhaul_margin_db": backhaul["margin_db"],
                    **metrics,
                    "_score": score,
                }
                if best is None or score < best["_score"]:
                    best = candidate
                if coverage == 1.0 and min_margin >= 0.0:
                    # Keep searching because a lower-energy full-cover point may exist.
                    pass
    if best is None:
        raise RuntimeError("No feasible relay candidate found in P1 search window")
    best.pop("_score", None)
    chosen_point = (best["lon"], best["lat"], best["altitude_m"])
    backhaul_certificate = interval_link_certificate(
        dem, chosen_point, chosen_point, gateway, thresholds["relay_gateway"], freq, obs
    )
    if not backhaul_certificate["certified_available"]:
        raise RuntimeError("Sampled relay candidate failed conservative backhaul certificate")
    best["backhaul_certificate_margin_db"] = backhaul_certificate["margin_lower_db"]
    best["backhaul_certificate_clearance_m"] = backhaul_certificate["min_clearance_lower_m"]
    return best


def adaptive_combined_check(
    dem: DemGrid,
    depot: Node,
    phases: list[dict[str, Any]],
    relay_solution: dict[str, Any],
    comm: dict[str, float],
    thresholds: dict[str, float],
    tol_s: float = 0.1,
) -> dict[str, Any]:
    gateway = (depot.lon, depot.lat, depot.ground_m + comm["天线离地高度（m）"])
    relay_point = None
    if relay_solution.get("needed"):
        relay_point = (
            relay_solution["lon"],
            relay_solution["lat"],
            relay_solution["altitude_m"],
        )
    freq = comm["载波频率（MHz）"]
    obs = comm["地形遮挡附加损耗（dB）"]

    back_static = None
    if relay_point is not None:
        back_static = interval_link_certificate(
            dem, relay_point, relay_point, gateway, thresholds["relay_gateway"], freq, obs
        )

    def evaluate(t: float) -> tuple[bool, float]:
        pos = position_at(phases, t)
        direct = link_state(dem, pos, gateway, thresholds["transport_gateway"], freq, obs)
        options = [float(direct["margin_db"])] if direct["available"] else []
        if relay_point is not None and back_static is not None and back_static["certified_available"]:
            access = link_state(dem, pos, relay_point, thresholds["transport_relay"], freq, obs)
            if access["available"]:
                options.append(float(min(access["margin_db"], back_static["margin_lower_db"])))
        return bool(options), max(options, default=float(direct["margin_db"]))

    def certify(t0: float, t1: float) -> tuple[bool, float, dict[str, Any]]:
        p0, p1 = position_at(phases, t0), position_at(phases, t1)
        direct = interval_link_certificate(
            dem, p0, p1, gateway, thresholds["transport_gateway"], freq, obs
        )
        if direct["certified_available"]:
            return True, float(direct["margin_lower_db"]), {
                "mode": "direct", "direct": direct, "access": None
            }
        candidates = [(False, direct["margin_lower_db"], "direct")]
        access = None
        if relay_point is not None and back_static is not None and back_static["certified_available"]:
            access = interval_link_certificate(
                dem, p0, p1, relay_point, thresholds["transport_relay"], freq, obs
            )
            relay_margin = min(float(access["margin_lower_db"]), float(back_static["margin_lower_db"]))
            candidates.append((access["certified_available"], relay_margin, "relay"))
        feasible = [item for item in candidates if item[0]]
        if feasible:
            chosen = max(feasible, key=lambda x: x[1])
            return True, float(chosen[1]), {"mode": chosen[2], "direct": direct, "access": access}
        return False, max(float(x[1]) for x in candidates), {"mode": "unresolved", "direct": direct, "access": access}

    leaves: list[dict[str, Any]] = []
    for phase in phases:
        phase_plan_m = horizontal_distance_m(*phase["p0"][:2], *phase["p1"][:2])
        initial_parts = max(1, int(math.ceil(phase_plan_m / 300.0)))
        cuts = np.linspace(float(phase["t0"]), float(phase["t1"]), initial_parts + 1)
        stack = [(float(cuts[i]), float(cuts[i + 1])) for i in range(initial_parts)]
        while stack:
            t0, t1 = stack.pop()
            available, margin_lb, evidence = certify(t0, t1)
            if available:
                leaves.append(
                    {
                        "t0": t0,
                        "t1": t1,
                        "available": True,
                        "margin_lower_db": margin_lb,
                        "unresolved": False,
                        "mode": evidence["mode"],
                    }
                )
            elif t1 - t0 <= tol_s + 1e-12:
                # A leaf that cannot be proved is deliberately treated as unavailable.
                leaves.append(
                    {
                        "t0": t0,
                        "t1": t1,
                        "available": False,
                        "margin_lower_db": margin_lb,
                        "unresolved": True,
                        "mode": "unresolved",
                    }
                )
            else:
                tm = (t0 + t1) / 2.0
                stack.append((tm, t1))
                stack.append((t0, tm))
    outage = [x for x in leaves if not x["available"]]
    unresolved = [x for x in leaves if x["unresolved"]]

    # Required independent cross-check. This does not replace the interval certificate.
    # Independent M1-contract cross-check. It supplements rather than replaces
    # the conservative interval proof above.
    grid_step_s = 0.05
    grid_times = np.arange(phases[0]["t0"], phases[-1]["t1"] + 1e-12, grid_step_s)
    if grid_times[-1] < phases[-1]["t1"]:
        grid_times = np.append(grid_times, phases[-1]["t1"])
    grid_values = [evaluate(float(t)) for t in grid_times]
    return {
        "tol_s": tol_s,
        "leaf_intervals": len(leaves),
        "outage_intervals": len(outage),
        "unresolved_intervals": len(unresolved),
        "max_unresolved_interval_s": max((x["t1"] - x["t0"] for x in unresolved), default=0.0),
        "min_certified_margin_lower_db": min(
            (x["margin_lower_db"] for x in leaves if x["available"]), default=float("-inf")
        ),
        "max_leaf_plan_sweep_m": max(
            horizontal_distance_m(*position_at(phases, x["t0"])[:2],
                                  *position_at(phases, x["t1"])[:2])
            for x in leaves
        ),
        "grid_step_s": grid_step_s,
        "grid_samples": len(grid_times),
        "grid_outages": sum(not value[0] for value in grid_values),
        "grid_min_margin_db": min(value[1] for value in grid_values),
    }


def charge_time_s(end_soc: float, full_charge_s: float) -> float:
    end_soc = min(max(end_soc, 0.0), 1.0)
    if end_soc < 0.9:
        return full_charge_s * (0.65 * (0.9 - end_soc) / 0.9 + 0.35)
    return full_charge_s * 0.35 * (1.0 - end_soc) / 0.1


def run_slice(project_root: Path) -> dict[str, Any]:
    data = load_inputs(project_root)
    nodes: dict[str, Node] = data["nodes"]
    boxes: pd.DataFrame = data["boxes"]
    types: dict[str, TransportType] = data["transport_types"]
    dem: DemGrid = data["dem"]
    depot = nodes["O01"]
    results_dir = project_root / "results"
    results_dir.mkdir(exist_ok=True)

    # P2 recommendation from M1: quantify local-plane distance error against haversine.
    distance_errors = []
    for service_id in sorted(k for k in nodes if k.startswith("S")):
        s = nodes[service_id]
        local = horizontal_distance_m(depot.lon, depot.lat, s.lon, s.lat)
        great = haversine_m(depot.lon, depot.lat, s.lon, s.lat)
        distance_errors.append({"service_id": service_id, "abs_m": abs(local - great), "rel": abs(local - great) / great})

    # Q1 slice uses all real S012 boxes and exact set-partition DP.
    q1_boxes = boxes[boxes["服务区编号"] == "S012"].copy()
    q1_batches = exact_q1_service(dem, depot, nodes["S012"], q1_boxes, types)
    q1_rows = []
    for idx, batch in enumerate(q1_batches, start=1):
        q1_rows.append(
            {
                "trip_id": f"P1-Q1-{idx:02d}",
                "service_id": "S012",
                "type_id": batch["type_id"],
                "box_ids": ";".join(batch["box_ids"]),
                "mass_kg": batch["mass_kg"],
                "volume_m3": batch["volume_m3"],
                "duration_s": batch["duration_s"],
                "energy_kwh": batch["energy_kwh"],
                "return_soc": batch["return_soc"],
            }
        )
    pd.DataFrame(q1_rows).to_csv(results_dir / "p1_q1_batches.csv", index=False, encoding="utf-8-sig")

    safe_payloads = {
        type_id: max_safe_payload(dem, depot, nodes["S012"], g) for type_id, g in types.items()
    }

    # Q2 slice explicitly tests the two medical+first boxes with effective 3600 s deadlines.
    hard_ids = ["S012-MED-01", "S014-MED-01"]
    q2_trips = []
    delivery_rows = []
    for idx, box_id in enumerate(hard_ids, start=1):
        batch = boxes[boxes["货箱编号"] == box_id].copy()
        service_id = str(batch.iloc[0]["服务区编号"])
        best = None
        for type_id, g in types.items():
            metrics = batch_metrics(dem, depot, nodes[service_id], g, batch)
            if (
                metrics["mass_kg"] <= g.payload_kg
                and metrics["volume_m3"] <= g.volume_m3
                and metrics["return_soc"] >= g.reserve - 1e-9
            ):
                timeline = single_service_timeline(dem, depot, nodes[service_id], g, batch, 0.0)
                score = (timeline["completions"][0]["completion_s"], timeline["energy_kwh"], type_id)
                if best is None or score < best[0]:
                    best = (score, type_id, timeline)
        if best is None:
            raise RuntimeError(f"No feasible direct trip for {box_id}")
        _, type_id, timeline = best
        same_type_units = [u["unit_id"] for u in data["transport_units"] if u["type_id"] == type_id]
        trip = {
            "trip_id": f"P1-Q2-{idx:02d}",
            "unit_id": same_type_units[idx - 1],
            "battery_id": f"{type_id}-BAT-{idx:02d}",
            "type_id": type_id,
            "service_id": service_id,
            **{k: v for k, v in timeline.items() if k != "completions"},
        }
        q2_trips.append(trip)
        for delivery in timeline["completions"]:
            delivery_rows.append({"trip_id": trip["trip_id"], **delivery})
    pd.DataFrame(delivery_rows).to_csv(results_dir / "p1_q2_deliveries.csv", index=False, encoding="utf-8-sig")

    # Q3 slice: full S012 direct trip, static relay candidate, relay energy and 0.1 s adaptive check.
    # Relay starts at t=0. The transport trip is delayed, when necessary, so takeoff is not
    # earlier than relay link establishment; this is the smallest real joint-scheduling action.
    relay_trip = q2_trips[0]
    relay_g = types[relay_trip["type_id"]]
    relay_batch = boxes[boxes["货箱编号"] == hard_ids[0]].copy()
    relay_timeline_base = single_service_timeline(dem, depot, nodes["S012"], relay_g, relay_batch, 0.0)
    phases_base = transport_trajectory(dem, depot, nodes["S012"], relay_g, relay_timeline_base)
    relay_solution = find_static_relay(
        dem, depot, data["relay_type"], phases_base, data["comm"], data["thresholds"]
    )
    prep_and_load_s = relay_g.prep_s + len(relay_batch) * relay_g.load_per_box_s
    q3_transport_start_s = max(0.0, relay_solution["link_ready_offset_s"] - prep_and_load_s)
    relay_timeline = single_service_timeline(
        dem, depot, nodes["S012"], relay_g, relay_batch, q3_transport_start_s
    )
    phases = transport_trajectory(dem, depot, nodes["S012"], relay_g, relay_timeline)
    adaptive = adaptive_combined_check(
        dem, depot, phases, relay_solution, data["comm"], data["thresholds"], tol_s=0.1
    )
    relay_solution["relay_start_s"] = 0.0
    relay_solution["relay_unit_id"] = "R01"
    relay_solution["energy_pack_id"] = "R-PACK-01"
    relay_solution["relay_takeoff_s"] = data["relay_type"].prep_s
    relay_solution["relay_arrival_s"] = data["relay_type"].prep_s + relay_solution["outbound_s"]
    relay_solution["link_ready_s"] = relay_solution["link_ready_offset_s"]
    relay_solution["service_end_s"] = relay_timeline["return_s"]
    relay_solution["relay_return_s"] = relay_timeline["return_s"] + relay_solution["return_s"]
    relay_solution["relay_available_s"] = (
        relay_solution["relay_return_s"] + data["relay_type"].turnaround_s
    )
    relay_solution["pack_task_start_s"] = 0.0
    relay_solution["pack_task_end_s"] = relay_solution["relay_return_s"]
    relay_solution["pack_charge_start_s"] = relay_solution["relay_return_s"]
    relay_solution["pack_charge_duration_s"] = charge_time_s(
        relay_solution["return_soc"], data["relay_inventory"]["full_charge_s"]
    )
    relay_solution["pack_charge_complete_s"] = (
        relay_solution["pack_charge_start_s"] + relay_solution["pack_charge_duration_s"]
    )
    relay_solution["transport_start_s"] = q3_transport_start_s
    relay_solution["transport_takeoff_s"] = relay_timeline["takeoff_s"]
    relay_solution["transport_return_s"] = relay_timeline["return_s"]
    relay_solution["transport_delivery_s"] = relay_timeline["completions"][0]["completion_s"]
    relay_solution["transport_hard_deadline_s"] = relay_timeline["completions"][0]["hard_deadline_s"]
    relay_solution["transport_hard_on_time"] = relay_timeline["completions"][0]["hard_on_time"]
    relay_solution["ready_before_transport_takeoff"] = (
        relay_solution["link_ready_s"] <= relay_timeline["takeoff_s"] + 1e-9
    )
    relay_row = {k: v for k, v in relay_solution.items() if isinstance(v, (int, float, bool, str))}
    relay_row.update({f"certificate_{k}": v for k, v in adaptive.items()})
    pd.DataFrame([relay_row]).to_csv(results_dir / "p1_q3_relay.csv", index=False, encoding="utf-8-sig")

    # Q4 slice: strict cross-group relay duplication and global (not per-group) inventory gap.
    q4_type = q2_trips[0]["type_id"]
    if any(trip["type_id"] != q4_type for trip in q2_trips):
        raise RuntimeError("P1 Q4 slice expects the two real hard-deadline trips to use one common type")
    uav_key = f"{q4_type}_uav"
    battery_key = f"{q4_type}_battery"
    group_needs = [
        {"group": 1, uav_key: 1, battery_key: 1, "relay_uav": 1, "relay_pack": 1},
        {"group": 2, uav_key: 1, battery_key: 1, "relay_uav": 1, "relay_pack": 1},
    ]
    inventory = {
        uav_key: sum(1 for u in data["transport_units"] if u["type_id"] == q4_type),
        battery_key: data["battery_inventory"][q4_type]["count"],
        "relay_uav": data["relay_inventory"]["units"],
        "relay_pack": data["relay_inventory"]["packs"],
    }
    centralized = {uav_key: 2, battery_key: 2, "relay_uav": 1, "relay_pack": 1}
    q4_rows = []
    for resource, stock in inventory.items():
        total_need = sum(row[resource] for row in group_needs)
        q4_rows.append(
            {
                "resource": resource,
                "total_group_need": total_need,
                "inventory": stock,
                "shortfall": max(0, total_need - stock),
                "central_need": centralized[resource],
                "partition_redundancy": total_need - centralized[resource],
            }
        )
    pd.DataFrame(q4_rows).to_csv(results_dir / "p1_q4_resources.csv", index=False, encoding="utf-8-sig")

    def all_finite(value: Any) -> bool:
        if isinstance(value, dict):
            return all(all_finite(v) for v in value.values())
        if isinstance(value, (list, tuple)):
            return all(all_finite(v) for v in value)
        if isinstance(value, (float, np.floating)):
            return math.isfinite(float(value))
        return True

    q4_formula_ok = all(
        row["shortfall"] == max(0, row["total_group_need"] - row["inventory"])
        and row["partition_redundancy"] == row["total_group_need"] - row["central_need"]
        for row in q4_rows
    )
    pre_sanity_objects = [q1_rows, q2_trips, delivery_rows, relay_solution, adaptive, q4_rows]

    report = {
        "mode": "slice",
        "seed": SEED,
        "python": sys.version,
        "platform": platform.platform(),
        "input_hashes": data["input_hashes"],
        "data_counts": {
            "services": 15,
            "boxes": int(len(boxes)),
            "demand_summary_records": int(len(data["summary"])),
            "transport_units": int(len(data["transport_units"])),
        },
        "distance_error": {
            "max_abs_m": max(x["abs_m"] for x in distance_errors),
            "max_rel": max(x["rel"] for x in distance_errors),
        },
        "link_thresholds_db": data["thresholds"],
        "q1": {
            "service": "S012",
            "safe_payload_kg": safe_payloads,
            "trip_count": len(q1_rows),
            "total_energy_kwh": sum(x["energy_kwh"] for x in q1_rows),
            "total_duration_s": sum(x["duration_s"] for x in q1_rows),
            "box_cover_count": len({b for x in q1_batches for b in x["box_ids"]}),
        },
        "q2": {
            "trips": q2_trips,
            "deliveries": delivery_rows,
            "hard_deadline_violations": sum(not row["hard_on_time"] for row in delivery_rows),
            "effective_deadlines_s": {row["box_id"]: row["hard_deadline_s"] for row in delivery_rows},
        },
        "q3": {"relay": relay_solution, "continuous_check": adaptive},
        "q4": q4_rows,
        "sanity": {
            "no_nan_inf": all_finite(pre_sanity_objects),
            "q1_unique_cover": (
                sorted(b for x in q1_batches for b in x["box_ids"])
                == sorted(q1_boxes["货箱编号"].tolist())
            ),
            "q2_zero_hard_late": all(row["hard_on_time"] for row in delivery_rows),
            "q3_zero_outage_intervals": (
                adaptive["outage_intervals"] == 0
                and adaptive["unresolved_intervals"] == 0
                and adaptive["grid_outages"] == 0
            ),
            "q3_relay_ready_before_takeoff": bool(relay_solution["ready_before_transport_takeoff"]),
            "q4_global_inventory_formula": q4_formula_ok,
        },
    }
    for obj in [report]:
        encoded = json.dumps(obj, allow_nan=False, ensure_ascii=False, indent=2)
        (results_dir / "p1_slice.json").write_text(encoded, encoding="utf-8")
    return report


def route_timeline(
    dem: DemGrid,
    depot: Node,
    nodes: dict[str, Node],
    g: TransportType,
    boxes: pd.DataFrame,
    stops: list[dict[str, Any]],
    start_s: float,
) -> dict[str, Any] | None:
    """Evaluate one multi-stop transport sortie with decreasing payload."""

    indexed = boxes.set_index("货箱编号", drop=False)
    all_ids = [box_id for stop in stops for box_id in stop["box_ids"]]
    batch = indexed.loc[all_ids]
    total_mass = float(batch["单箱质量（kg）"].sum())
    total_volume = float(batch["单箱体积（m³）"].sum())
    if total_mass > g.payload_kg + 1e-9 or total_volume > g.volume_m3 + 1e-12:
        return None

    takeoff_s = start_s + g.prep_s + len(all_ids) * g.load_per_box_s
    current_node = depot
    current_time = takeoff_s
    remaining_payload = total_mass
    energy = 0.0
    completions: list[dict[str, Any]] = []
    leg_records: list[dict[str, Any]] = []
    service_records: list[dict[str, Any]] = []

    for stop in stops:
        service_id = str(stop["service_id"])
        service = nodes[service_id]
        leg = leg_metrics(dem, current_node, service, g, remaining_payload)
        arrival_s = current_time + leg["time_s"]
        leg_records.append(
            {
                "origin": current_node.node_id,
                "destination": service_id,
                "start_s": current_time,
                "end_s": arrival_s,
                "payload_kg": remaining_payload,
                **leg,
            }
        )
        energy += leg["energy_kwh"]
        stop_rows = indexed.loc[list(stop["box_ids"])].copy().reset_index(drop=True)
        stop_rows["_hard"] = stop_rows.apply(box_deadline, axis=1)
        stop_rows["_hard_sort"] = [float(x) if x is not None else float("inf") for x in stop_rows["_hard"]]
        stop_rows = stop_rows.sort_values(
            ["_hard_sort", "应急优先系数", "货箱编号"], ascending=[True, False, True]
        )
        handover_start = arrival_s + g.base_handover_s
        for order, (_, row) in enumerate(stop_rows.iterrows(), start=1):
            completion_s = handover_start + order * g.handover_per_box_s
            hard = box_deadline(row)
            expected = float(row["期望送达时间（s）"])
            completions.append(
                {
                    "box_id": str(row["货箱编号"]),
                    "service_id": service_id,
                    "completion_s": completion_s,
                    "hard_deadline_s": hard,
                    "hard_on_time": hard is None or completion_s <= hard + 1e-9,
                    "expected_s": expected,
                    "priority": float(row["应急优先系数"]),
                    "tardiness_s": max(0.0, completion_s - expected),
                }
            )
        depart_s = arrival_s + g.base_handover_s + len(stop_rows) * g.handover_per_box_s
        service_records.append(
            {"service_id": service_id, "arrival_s": arrival_s, "depart_s": depart_s}
        )
        remaining_payload -= float(stop_rows["单箱质量（kg）"].sum())
        current_node = service
        current_time = depart_s

    back = leg_metrics(dem, current_node, depot, g, 0.0)
    return_s = current_time + back["time_s"]
    leg_records.append(
        {
            "origin": current_node.node_id,
            "destination": depot.node_id,
            "start_s": current_time,
            "end_s": return_s,
            "payload_kg": 0.0,
            **back,
        }
    )
    energy += back["energy_kwh"]
    return_soc = 1.0 - energy / g.energy_kwh
    if return_soc < g.reserve - 1e-9:
        return None
    return {
        "start_s": start_s,
        "takeoff_s": takeoff_s,
        "return_s": return_s,
        "duration_s": return_s - start_s,
        "payload_kg": total_mass,
        "volume_m3": total_volume,
        "energy_kwh": energy,
        "return_soc": return_soc,
        "completions": completions,
        "leg_records": leg_records,
        "service_records": service_records,
        "stops": stops,
    }


def route_trajectory(
    dem: DemGrid,
    depot: Node,
    nodes: dict[str, Node],
    g: TransportType,
    timeline: dict[str, Any],
) -> list[dict[str, Any]]:
    """Expand a route timeline into linear climb/cruise/descent and service phases."""

    phases: list[dict[str, Any]] = []
    for leg_index, leg in enumerate(timeline["leg_records"], start=1):
        a, b = nodes[leg["origin"]], nodes[leg["destination"]]
        t0 = float(leg["start_s"])
        t1 = t0 + leg["climb_m"] / g.climb_mps
        t2 = t1 + leg["distance_m"] / g.cruise_mps
        t3 = float(leg["end_s"])
        phases.extend(
            [
                {"name": f"leg{leg_index}_climb", "t0": t0, "t1": t1,
                 "p0": (a.lon, a.lat, a.operation_m),
                 "p1": (a.lon, a.lat, leg["cruise_alt_m"])},
                {"name": f"leg{leg_index}_cruise", "t0": t1, "t1": t2,
                 "p0": (a.lon, a.lat, leg["cruise_alt_m"]),
                 "p1": (b.lon, b.lat, leg["cruise_alt_m"])},
                {"name": f"leg{leg_index}_descent", "t0": t2, "t1": t3,
                 "p0": (b.lon, b.lat, leg["cruise_alt_m"]),
                 "p1": (b.lon, b.lat, b.operation_m)},
            ]
        )
        if b.node_id != "O01":
            service = next(x for x in timeline["service_records"] if x["service_id"] == b.node_id)
            if service["depart_s"] > service["arrival_s"]:
                phases.append(
                    {"name": f"service_{b.node_id}", "t0": service["arrival_s"],
                     "t1": service["depart_s"],
                     "p0": (b.lon, b.lat, b.operation_m),
                     "p1": (b.lon, b.lat, b.operation_m)}
                )
    phases.sort(key=lambda x: (x["t0"], x["t1"], x["name"]))
    return [p for p in phases if p["t1"] > p["t0"] + 1e-9]


def _trip_spec_key(spec: dict[str, Any], boxes: pd.DataFrame) -> tuple[float, float, str]:
    indexed = boxes.set_index("货箱编号", drop=False)
    rows = indexed.loc[[x for stop in spec["stops"] for x in stop["box_ids"]]]
    hard = [box_deadline(row) for _, row in rows.iterrows()]
    hard_values = [x for x in hard if x is not None]
    return (
        min(hard_values, default=float("inf")),
        float(rows["期望送达时间（s）"].min()),
        str(min(rows["货箱编号"])),
    )


def _build_q2_specs(
    data: dict[str, Any], q1_by_service: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    boxes: pd.DataFrame = data["boxes"]
    hard_specs: list[dict[str, Any]] = []
    soft_specs: list[dict[str, Any]] = []
    for service_id in sorted(k for k in data["nodes"] if k.startswith("S")):
        service_boxes = boxes[boxes["服务区编号"] == service_id].copy()
        service_boxes["_hard"] = service_boxes.apply(box_deadline, axis=1)
        hard_ids = service_boxes.loc[service_boxes["_hard"].notna(), "货箱编号"].tolist()
        if hard_ids:
            hard_specs.append({"stops": [{"service_id": service_id, "box_ids": hard_ids}], "kind": "hard"})
        soft = service_boxes[service_boxes["_hard"].isna()].drop(columns=["_hard"])
        if len(soft):
            for batch in exact_q1_service(
                data["dem"], data["nodes"]["O01"], data["nodes"][service_id], soft,
                data["transport_types"],
            ):
                soft_specs.append(
                    {"stops": [{"service_id": service_id, "box_ids": list(batch["box_ids"])}],
                     "kind": "soft"}
                )

    # Pair compatible soft single-service batches when the merged route saves energy.
    active = soft_specs[:]
    while True:
        best: tuple[float, int, int, list[dict[str, Any]]] | None = None
        for i in range(len(active)):
            for j in range(i + 1, len(active)):
                if len(active[i]["stops"]) != 1 or len(active[j]["stops"]) != 1:
                    continue
                if active[i]["stops"][0]["service_id"] == active[j]["stops"][0]["service_id"]:
                    continue
                individual = 0.0
                possible = True
                for spec in (active[i], active[j]):
                    values = [
                        route_timeline(data["dem"], data["nodes"]["O01"], data["nodes"], g,
                                       boxes, spec["stops"], 0.0)
                        for g in data["transport_types"].values()
                    ]
                    values = [x for x in values if x is not None]
                    if not values:
                        possible = False
                        break
                    individual += min(x["energy_kwh"] for x in values)
                if not possible:
                    continue
                for order in ([active[i]["stops"][0], active[j]["stops"][0]],
                              [active[j]["stops"][0], active[i]["stops"][0]]):
                    merged = [
                        route_timeline(data["dem"], data["nodes"]["O01"], data["nodes"], g,
                                       boxes, list(order), 0.0)
                        for g in data["transport_types"].values()
                    ]
                    merged = [x for x in merged if x is not None]
                    if not merged:
                        continue
                    saving = individual - min(x["energy_kwh"] for x in merged)
                    if saving > 1e-9 and (best is None or saving > best[0] + 1e-12):
                        best = (saving, i, j, list(order))
        if best is None:
            break
        _, i, j, order = best
        active = [x for k, x in enumerate(active) if k not in (i, j)] + [
            {"stops": order, "kind": "soft"}
        ]
    return sorted(hard_specs + active, key=lambda x: _trip_spec_key(x, boxes))


def _schedule_q2(data: dict[str, Any], specs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    boxes, dem, nodes = data["boxes"], data["dem"], data["nodes"]
    depot = nodes["O01"]
    units_by_type: dict[str, list[str]] = {
        type_id: [u["unit_id"] for u in data["transport_units"] if u["type_id"] == type_id]
        for type_id in data["transport_types"]
    }
    battery_ids = {
        type_id: [f"{type_id}-BAT-{i:02d}" for i in range(1, info["count"] + 1)]
        for type_id, info in data["battery_inventory"].items()
    }
    unit_ready = {u["unit_id"]: 0.0 for u in data["transport_units"]}
    battery_ready = {battery: 0.0 for values in battery_ids.values() for battery in values}
    scheduled: list[dict[str, Any]] = []

    def options(spec: dict[str, Any], forced_unit: str | None = None) -> list[tuple[Any, ...]]:
        candidates = []
        for type_id, g in data["transport_types"].items():
            units = [forced_unit] if forced_unit in units_by_type[type_id] else units_by_type[type_id]
            if forced_unit is not None and forced_unit not in units_by_type[type_id]:
                continue
            for unit_id in units:
                for battery_id in battery_ids[type_id]:
                    start = max(unit_ready[unit_id], battery_ready[battery_id])
                    timeline = route_timeline(dem, depot, nodes, g, boxes, spec["stops"], start)
                    if timeline is None:
                        continue
                    hard_late = sum(not x["hard_on_time"] for x in timeline["completions"])
                    hard_max = max(
                        (max(0.0, x["completion_s"] - x["hard_deadline_s"])
                         for x in timeline["completions"] if x["hard_deadline_s"] is not None),
                        default=0.0,
                    )
                    wtd = sum(
                        x["priority"] * x["tardiness_s"] / x["expected_s"]
                        for x in timeline["completions"] if x["hard_deadline_s"] is None
                    )
                    score = (hard_late, hard_max, wtd, max(x["completion_s"] for x in timeline["completions"]),
                             timeline["energy_kwh"], timeline["return_s"], type_id, unit_id, battery_id)
                    candidates.append((score, type_id, unit_id, battery_id, timeline))
        return candidates

    urgent = [x for x in specs if _trip_spec_key(x, boxes)[0] == 3600.0]
    remaining = [x for x in specs if x not in urgent]
    all_units = [u["unit_id"] for u in data["transport_units"]]
    if len(urgent) == len(all_units):
        pair_options: dict[tuple[int, str], tuple[Any, ...]] = {}
        for job_index, spec in enumerate(urgent):
            for unit_id in all_units:
                cands = options(spec, forced_unit=unit_id)
                if cands:
                    pair_options[(job_index, unit_id)] = min(cands, key=lambda x: x[0])
        best_assignment = None
        for perm in itertools.permutations(all_units):
            chosen = [pair_options.get((i, perm[i])) for i in range(len(urgent))]
            if any(x is None for x in chosen):
                continue
            assert all(x is not None for x in chosen)
            score = (
                max(x[0][1] for x in chosen),
                sum(x[0][0] for x in chosen),
                max(x[4]["completions"][-1]["completion_s"] for x in chosen),
                sum(x[4]["energy_kwh"] for x in chosen),
                perm,
            )
            if best_assignment is None or score < best_assignment[0]:
                best_assignment = (score, chosen)
        if best_assignment is None:
            raise RuntimeError("No feasible assignment for eight 3600-second hard trips")
        initial_choices = best_assignment[1]
    else:
        initial_choices = [min(options(spec), key=lambda x: x[0]) for spec in urgent]

    ordered_choices: list[tuple[dict[str, Any], tuple[Any, ...]]] = list(zip(urgent, initial_choices))
    for spec in remaining:
        candidates = options(spec)
        if not candidates:
            raise RuntimeError(f"No feasible resource assignment for {spec}")
        ordered_choices.append((spec, min(candidates, key=lambda x: x[0])))
        # Commit immediately so later options see updated readiness.
        _, type_id, unit_id, battery_id, timeline = ordered_choices[-1][1]
        unit_ready[unit_id] = timeline["return_s"]
        battery_ready[battery_id] = timeline["return_s"] + charge_time_s(
            timeline["return_soc"], data["battery_inventory"][type_id]["full_charge_s"]
        )

    # Urgent assignments were optimized jointly at t=0 and must be committed before
    # reconstructing the complete list; remaining choices are already committed above.
    for spec, choice in ordered_choices[: len(urgent)]:
        _, type_id, unit_id, battery_id, timeline = choice
        unit_ready[unit_id] = max(unit_ready[unit_id], timeline["return_s"])
        battery_ready[battery_id] = max(
            battery_ready[battery_id],
            timeline["return_s"] + charge_time_s(
                timeline["return_soc"], data["battery_inventory"][type_id]["full_charge_s"]
            ),
        )

    # The loop above selected remaining trips before urgent readiness was committed.
    # Re-schedule deterministically from scratch, preserving the optimized urgent assignment.
    unit_ready = {u["unit_id"]: 0.0 for u in data["transport_units"]}
    battery_ready = {battery: 0.0 for values in battery_ids.values() for battery in values}
    final_sequence: list[tuple[dict[str, Any], str | None]] = [
        (spec, choice[2]) for spec, choice in ordered_choices[: len(urgent)]
    ] + [(spec, None) for spec in remaining]
    for trip_index, (spec, forced_unit) in enumerate(final_sequence, start=1):
        candidates = options(spec, forced_unit=forced_unit)
        if not candidates:
            raise RuntimeError(f"No feasible re-scheduled option for {spec}")
        _, type_id, unit_id, battery_id, timeline = min(candidates, key=lambda x: x[0])
        trip_id = f"T{trip_index:03d}"
        charge_duration = charge_time_s(
            timeline["return_soc"], data["battery_inventory"][type_id]["full_charge_s"]
        )
        trip = {
            "trip_id": trip_id,
            "unit_id": unit_id,
            "type_id": type_id,
            "battery_id": battery_id,
            "route": [x["service_id"] for x in spec["stops"]],
            "box_ids": [x for stop in spec["stops"] for x in stop["box_ids"]],
            **{k: v for k, v in timeline.items() if k not in ("completions", "stops")},
            "battery_charge_start_s": timeline["return_s"],
            "battery_charge_duration_s": charge_duration,
            "battery_charge_complete_s": timeline["return_s"] + charge_duration,
        }
        scheduled.append(trip)
        unit_ready[unit_id] = timeline["return_s"]
        battery_ready[battery_id] = timeline["return_s"] + charge_duration
        for completion in timeline["completions"]:
            completion["trip_id"] = trip_id
    deliveries = [
        completion
        for trip in scheduled
        for completion in route_timeline(
            dem, depot, nodes, data["transport_types"][trip["type_id"]], boxes,
            [{"service_id": sid, "box_ids": [b for b in trip["box_ids"]
                                               if str(boxes.set_index("货箱编号").loc[b, "服务区编号"]) == sid]}
             for sid in trip["route"]],
            trip["start_s"],
        )["completions"]
    ]
    for trip in scheduled:
        for row in deliveries:
            if row["box_id"] in trip["box_ids"]:
                row["trip_id"] = trip["trip_id"]
    return scheduled, deliveries


def adaptive_multi_relay_check(
    dem: DemGrid,
    depot: Node,
    phases: list[dict[str, Any]],
    relay_points: list[tuple[float, float, float]],
    comm: dict[str, float],
    thresholds: dict[str, float],
    tol_s: float = 0.1,
    grid_step_s: float = 0.5,
) -> dict[str, Any]:
    """Continuous combined-link proof for one route and zero or more active relays."""

    gateway = (depot.lon, depot.lat, depot.ground_m + comm["天线离地高度（m）"])
    freq, obs = comm["载波频率（MHz）"], comm["地形遮挡附加损耗（dB）"]
    backhaul = [
        interval_link_certificate(dem, point, point, gateway, thresholds["relay_gateway"], freq, obs)
        for point in relay_points
    ]
    if any(not x["certified_available"] for x in backhaul):
        raise RuntimeError("Selected full-run relay point lacks a conservative backhaul certificate")

    def certify(t0: float, t1: float) -> tuple[bool, float, str]:
        p0, p1 = position_at(phases, t0), position_at(phases, t1)
        direct = interval_link_certificate(
            dem, p0, p1, gateway, thresholds["transport_gateway"], freq, obs
        )
        if direct["certified_available"]:
            return True, float(direct["margin_lower_db"]), "direct"
        feasible: list[tuple[float, str]] = []
        for index, (point, back) in enumerate(zip(relay_points, backhaul)):
            access = interval_link_certificate(
                dem, p0, p1, point, thresholds["transport_relay"], freq, obs
            )
            margin = min(float(access["margin_lower_db"]), float(back["margin_lower_db"]))
            if access["certified_available"]:
                feasible.append((margin, f"relay{index}"))
        if feasible:
            margin, mode = max(feasible)
            return True, margin, mode
        return False, float(direct["margin_lower_db"]), "unresolved"

    leaves: list[dict[str, Any]] = []
    for phase in phases:
        phase_plan_m = horizontal_distance_m(*phase["p0"][:2], *phase["p1"][:2])
        initial_parts = max(1, int(math.ceil(phase_plan_m / 300.0)))
        cuts = np.linspace(float(phase["t0"]), float(phase["t1"]), initial_parts + 1)
        stack = [(float(cuts[i]), float(cuts[i + 1])) for i in range(initial_parts)]
        while stack:
            t0, t1 = stack.pop()
            available, margin, mode = certify(t0, t1)
            if available:
                leaves.append({"t0": t0, "t1": t1, "mode": mode, "margin_lower_db": margin})
            elif t1 - t0 <= tol_s + 1e-12:
                leaves.append({"t0": t0, "t1": t1, "mode": "unresolved", "margin_lower_db": margin})
            else:
                tm = (t0 + t1) / 2.0
                stack.extend([(tm, t1), (t0, tm)])
    leaves.sort(key=lambda x: (x["t0"], x["t1"]))
    segments: list[dict[str, Any]] = []
    for leaf in leaves:
        if segments and segments[-1]["mode"] == leaf["mode"] and abs(segments[-1]["t1"] - leaf["t0"]) <= 1e-7:
            segments[-1]["t1"] = leaf["t1"]
            segments[-1]["margin_lower_db"] = min(
                segments[-1]["margin_lower_db"], leaf["margin_lower_db"]
            )
        else:
            segments.append(dict(leaf))

    grid_times = np.arange(phases[0]["t0"], phases[-1]["t1"] + 1e-12, grid_step_s)
    if grid_times[-1] < phases[-1]["t1"]:
        grid_times = np.append(grid_times, phases[-1]["t1"])
    grid_outages = 0
    grid_min_margin = float("inf")
    for t in grid_times:
        pos = position_at(phases, float(t))
        direct = link_state(dem, pos, gateway, thresholds["transport_gateway"], freq, obs)
        margins = [float(direct["margin_db"])] if direct["available"] else []
        for point, back in zip(relay_points, backhaul):
            access = link_state(dem, pos, point, thresholds["transport_relay"], freq, obs)
            if access["available"]:
                margins.append(min(float(access["margin_db"]), float(back["margin_lower_db"])))
        if not margins:
            grid_outages += 1
        else:
            grid_min_margin = min(grid_min_margin, max(margins))
    unresolved = [x for x in leaves if x["mode"] == "unresolved"]
    return {
        "leaf_intervals": len(leaves),
        "segments": segments,
        "unresolved_intervals": len(unresolved),
        "outage_intervals": len(unresolved),
        "min_margin_lower_db": min(
            (x["margin_lower_db"] for x in leaves if x["mode"] != "unresolved"),
            default=-1e9,
        ),
        "max_unresolved_interval_s": max((x["t1"] - x["t0"] for x in unresolved), default=0.0),
        "grid_step_s": grid_step_s,
        "grid_samples": len(grid_times),
        "grid_outages": grid_outages,
        "grid_min_margin_db": grid_min_margin if math.isfinite(grid_min_margin) else -1e9,
    }


def _trip_stops_from_record(trip: dict[str, Any], boxes: pd.DataFrame) -> list[dict[str, Any]]:
    service_by_box = boxes.set_index("货箱编号")["服务区编号"].to_dict()
    return [
        {"service_id": service_id,
         "box_ids": [box_id for box_id in trip["box_ids"] if service_by_box[box_id] == service_id]}
        for service_id in trip["route"]
    ]


def _schedule_q3_joint(
    data: dict[str, Any], q2_trips: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Wave-based joint transport/relay schedule with event-level resource accounting."""

    # Deterministic points obtained by search_relay_pair.py on 5 s blackout samples.
    # Every selected point is re-certified below, and every complete trajectory is
    # subsequently subjected to the continuous interval proof.
    points = {
        "P1A": (109.28277777777778, 23.026944444444446, 649.4981079101562),
        "P1B": (109.22277777777778, 23.040277777777778, 587.5166015625),
        "P2A": (109.20555555555556, 23.049444444444443, 703.3844604492188),
        "P2B": (109.22555555555556, 23.069444444444446, 626.3524169921875),
        "P3A": (109.23833333333333, 23.052777777777777, 534.8773498535156),
    }
    wave_definitions = [
        ("W1", list(range(0, 8)), ["P1A", "P1B"]),
        ("W2", list(range(8, 12)), ["P2A", "P2B"]),
        ("W3", list(range(12, 15)), ["P3A"]),
        ("W4", list(range(15, 17)), []),
        ("W5", list(range(17, 19)), ["P1B", "P2A"]),
        ("W6", list(range(19, 21)), ["P2A", "P2B"]),
        ("W7", [21], ["P2A", "P2B"]),
        ("W8", list(range(22, 26)), ["P1A", "P1B"]),
    ]
    boxes, dem, nodes, types = data["boxes"], data["dem"], data["nodes"], data["transport_types"]
    depot = nodes["O01"]
    unit_ready = {u["unit_id"]: 0.0 for u in data["transport_units"]}
    battery_ready = {
        f"{type_id}-BAT-{index:02d}": 0.0
        for type_id, info in data["battery_inventory"].items()
        for index in range(1, info["count"] + 1)
    }
    relay_unit_ready = {"R01": 0.0, "R02": 0.0}
    pack_ready = {f"R-PACK-{index:02d}": 0.0 for index in range(1, data["relay_inventory"]["packs"] + 1)}
    q3_trips: list[dict[str, Any]] = []
    relay_missions: list[dict[str, Any]] = []
    communication_rows: list[dict[str, Any]] = []
    proof_summaries: list[dict[str, Any]] = []
    relay_type = data["relay_type"]

    for wave_name, trip_indices, point_names in wave_definitions:
        selected = [q2_trips[i] for i in trip_indices]
        assignments = []
        reserved_packs: set[str] = set()
        for point_index, point_name in enumerate(point_names):
            unit_id = f"R{point_index + 1:02d}"
            eligible_packs = [p for p in pack_ready if p not in reserved_packs]
            pack_id = min(
                eligible_packs,
                key=lambda p: (max(pack_ready[p], relay_unit_ready[unit_id]), p),
            )
            reserved_packs.add(pack_id)
            start_s = max(relay_unit_ready[unit_id], pack_ready[pack_id])
            point = points[point_name]
            preliminary = relay_flight_metrics(dem, depot, relay_type, *point, 0.0)
            assignments.append(
                {"point_name": point_name, "point": point, "unit_id": unit_id, "pack_id": pack_id,
                 "start_s": start_s, "preliminary": preliminary,
                 "link_ready_s": start_s + preliminary["link_ready_offset_s"]}
            )
        common_start = max(
            [unit_ready[x["unit_id"]] for x in selected]
            + [battery_ready[x["battery_id"]] for x in selected]
            + [0.0]
        )
        if assignments:
            latest_link = max(x["link_ready_s"] for x in assignments)
            min_ground_prep = min(
                types[x["type_id"]].prep_s + len(x["box_ids"]) * types[x["type_id"]].load_per_box_s
                for x in selected
            )
            common_start = max(common_start, latest_link - min_ground_prep)

        wave_trips: list[dict[str, Any]] = []
        for original in selected:
            g = types[original["type_id"]]
            timeline = route_timeline(
                dem, depot, nodes, g, boxes, _trip_stops_from_record(original, boxes), common_start
            )
            if timeline is None:
                raise RuntimeError(f"Q3 shifted route became infeasible: {original['trip_id']}")
            charge_duration = charge_time_s(
                timeline["return_soc"], data["battery_inventory"][original["type_id"]]["full_charge_s"]
            )
            shifted = {
                **original,
                **{k: v for k, v in timeline.items() if k not in ("completions", "stops")},
                "wave": wave_name,
                "battery_charge_start_s": timeline["return_s"],
                "battery_charge_duration_s": charge_duration,
                "battery_charge_complete_s": timeline["return_s"] + charge_duration,
                "completions": timeline["completions"],
            }
            wave_trips.append(shifted)
            q3_trips.append(shifted)
            unit_ready[shifted["unit_id"]] = timeline["return_s"]
            battery_ready[shifted["battery_id"]] = timeline["return_s"] + charge_duration

        service_end = max((x["return_s"] for x in wave_trips), default=common_start)
        mission_ids = []
        for assignment in assignments:
            service_s = max(0.0, service_end - assignment["link_ready_s"])
            metrics = relay_flight_metrics(
                dem, depot, relay_type, *assignment["point"], service_s
            )
            if not metrics["feasible_energy"]:
                raise RuntimeError(f"Relay energy infeasible in {wave_name} at {assignment['point_name']}")
            mission_id = f"R-{len(relay_missions) + 1:03d}"
            relay_return_s = service_end + metrics["return_s"]
            charge_duration = charge_time_s(metrics["return_soc"], data["relay_inventory"]["full_charge_s"])
            mission = {
                "mission_id": mission_id,
                "wave": wave_name,
                "point_name": assignment["point_name"],
                "relay_unit_id": assignment["unit_id"],
                "energy_pack_id": assignment["pack_id"],
                "start_s": assignment["start_s"],
                "lon": assignment["point"][0], "lat": assignment["point"][1],
                "altitude_m": assignment["point"][2],
                "ground_m": dem.elevation(assignment["point"][0], assignment["point"][1]),
                "link_ready_s": assignment["link_ready_s"],
                "service_end_s": service_end,
                "return_s": relay_return_s,
                "available_s": relay_return_s + relay_type.turnaround_s,
                "energy_kwh": metrics["energy_kwh"], "return_soc": metrics["return_soc"],
                "pack_charge_start_s": relay_return_s,
                "pack_charge_duration_s": charge_duration,
                "pack_charge_complete_s": relay_return_s + charge_duration,
                "served_trip_ids": [x["trip_id"] for x in wave_trips],
            }
            relay_missions.append(mission)
            mission_ids.append(mission_id)
            relay_unit_ready[assignment["unit_id"]] = mission["available_s"]
            pack_ready[assignment["pack_id"]] = mission["pack_charge_complete_s"]

        active_points = [points[name] for name in point_names]
        for trip in wave_trips:
            phases = route_trajectory(dem, depot, nodes, types[trip["type_id"]], trip)
            proof = adaptive_multi_relay_check(
                dem, depot, phases, active_points, data["comm"], data["thresholds"],
                tol_s=0.1, grid_step_s=0.5,
            )
            proof_summaries.append(
                {"trip_id": trip["trip_id"], "wave": wave_name,
                 **{k: v for k, v in proof.items() if k != "segments"}}
            )
            for segment in proof["segments"]:
                if segment["mode"].startswith("relay"):
                    relay_index = int(segment["mode"].replace("relay", ""))
                    assurance = "中继"
                    mission_id = mission_ids[relay_index]
                elif segment["mode"] == "direct":
                    assurance, mission_id = "直连", ""
                else:
                    assurance, mission_id = "未证明", ""
                communication_rows.append(
                    {"trip_id": trip["trip_id"], "phase": segment["mode"],
                     "start_s": segment["t0"], "end_s": segment["t1"],
                     "assurance": assurance, "relay_mission_id": mission_id,
                     "margin_lower_db": segment["margin_lower_db"]}
                )

    hard_late = [
        completion for trip in q3_trips for completion in trip["completions"]
        if completion["hard_deadline_s"] is not None and not completion["hard_on_time"]
    ]
    transport_makespan_s = max(x["return_s"] for x in q3_trips)
    relay_makespan_s = max(x["return_s"] for x in relay_missions)
    joint_makespan_s = max(transport_makespan_s, relay_makespan_s)
    summary = {
        "hard_late_count": len(hard_late),
        "outage_interval_count": sum(x["outage_intervals"] for x in proof_summaries),
        "grid_outage_count": sum(x["grid_outages"] for x in proof_summaries),
        "min_margin_lower_db": min(x["min_margin_lower_db"] for x in proof_summaries),
        "transport_makespan_s": transport_makespan_s,
        "relay_makespan_s": relay_makespan_s,
        "joint_makespan_s": joint_makespan_s,
        "makespan_s": joint_makespan_s,
        "transport_energy_kwh": sum(x["energy_kwh"] for x in q3_trips),
        "relay_energy_kwh": sum(x["energy_kwh"] for x in relay_missions),
        "proofs": proof_summaries,
    }
    return q3_trips, relay_missions, communication_rows, summary


def _max_overlap(intervals: list[tuple[float, float]]) -> int:
    events = [(start, 1) for start, end in intervals if end > start] + [
        (end, -1) for start, end in intervals if end > start
    ]
    active = best = 0
    for _, delta in sorted(events, key=lambda x: (x[0], x[1])):
        active += delta
        best = max(best, active)
    return best


def _solve_q4_partitions(
    data: dict[str, Any],
    q3_trips: list[dict[str, Any]],
    relay_missions: list[dict[str, Any]],
    communication_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    services = sorted(k for k in data["nodes"] if k.startswith("S"))
    parent = {s: s for s in services}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    for trip in q3_trips:
        for service in trip["route"][1:]:
            union(trip["route"][0], service)
    components: dict[str, list[str]] = {}
    for service in services:
        components.setdefault(find(service), []).append(service)
    blocks = sorted(components.values(), key=lambda x: x[0])

    inventory = {
        "A_uav": 4, "B_uav": 2, "C_uav": 2,
        "A_battery": 6, "B_battery": 4, "C_battery": 4,
        "relay_uav": data["relay_inventory"]["units"],
        "relay_pack": data["relay_inventory"]["packs"],
    }

    # A relay mission belongs to a partition only when the final communication
    # segmentation actually assigns that mission to one of the partition's
    # transport trips.  ``served_trip_ids`` is the wave-level candidate list
    # used during Q3 coverage search and can include trips that remained on a
    # direct link or were assigned to another relay; using it here would copy
    # unnecessary relay tasks into Q4 and overstate independent resources.
    actual_trips_by_mission: dict[str, set[str]] = {}
    for row in communication_rows:
        mission_id = row.get("relay_mission_id")
        if mission_id:
            actual_trips_by_mission.setdefault(str(mission_id), set()).add(str(row["trip_id"]))

    def resources_for(group: set[str]) -> tuple[dict[str, int], float, float]:
        trips = [x for x in q3_trips if set(x["route"]) & group]
        trip_ids = {x["trip_id"] for x in trips}
        missions = [
            x for x in relay_missions
            if trip_ids & actual_trips_by_mission.get(x["mission_id"], set())
        ]
        needs: dict[str, int] = {}
        for type_id in ("A", "B", "C"):
            typed = [x for x in trips if x["type_id"] == type_id]
            needs[f"{type_id}_uav"] = _max_overlap([(x["start_s"], x["return_s"]) for x in typed])
            needs[f"{type_id}_battery"] = _max_overlap(
                [(x["start_s"], x["battery_charge_complete_s"]) for x in typed]
            )
        needs["relay_uav"] = _max_overlap([(x["start_s"], x["available_s"]) for x in missions])
        needs["relay_pack"] = _max_overlap(
            [(x["start_s"], x["pack_charge_complete_s"]) for x in missions]
        )
        workload = sum(x["return_s"] - x["start_s"] for x in trips) + sum(
            x["available_s"] - x["start_s"] for x in missions
        )
        # The task statement defines group completion by the last transport or
        # copied relay mission returning to O01; turnaround/charging is a
        # resource constraint, not part of completion time.
        completion = max(
            [x["return_s"] for x in trips]
            + [x["return_s"] for x in missions]
            + [0.0]
        )
        return needs, workload, completion

    central, _, _ = resources_for(set(services))
    output_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for k in (2, 3):
        best = None
        for labels_tail in itertools.product(range(k), repeat=len(blocks) - 1):
            labels = (0,) + labels_tail
            if set(labels) != set(range(k)):
                continue
            groups = [set() for _ in range(k)]
            for block, label in zip(blocks, labels):
                groups[label].update(block)
            group_values = [resources_for(group) for group in groups]
            total_need = {key: sum(value[0][key] for value in group_values) for key in inventory}
            shortage = sum(max(0, total_need[key] - inventory[key]) for key in inventory)
            total_configuration = sum(total_need.values())
            workloads = np.asarray([value[1] for value in group_values], dtype=float)
            cv = float(np.std(workloads, ddof=0) / np.mean(workloads))
            completion_range = max(value[2] for value in group_values) - min(value[2] for value in group_values)
            canonical = tuple(tuple(sorted(group)) for group in groups)
            score = (shortage, total_configuration, cv, completion_range, canonical)
            if best is None or score < best[0]:
                best = (score, groups, group_values, total_need)
        if best is None:
            raise RuntimeError(f"No Q4 partition for K={k}")
        _, groups, group_values, total_need = best
        for group_index, (group, (needs, workload, completion)) in enumerate(zip(groups, group_values), start=1):
            output_rows.append(
                {"K": k, "group": group_index, "services": ";".join(sorted(group)), **needs,
                 "workload_h": workload / 3600.0, "completion_s": completion}
            )
        for resource in inventory:
            summary_rows.append(
                {"K": k, "resource": resource, "total_group_need": total_need[resource],
                 "inventory": inventory[resource],
                 "shortfall": max(0, total_need[resource] - inventory[resource]),
                 "central_need": central[resource],
                 "partition_redundancy": total_need[resource] - central[resource]}
            )
    return output_rows, summary_rows


def run_full(project_root: Path) -> dict[str, Any]:
    data = load_inputs(project_root)
    results_dir = project_root / "results"
    results_dir.mkdir(exist_ok=True)
    nodes, boxes, types, dem = data["nodes"], data["boxes"], data["transport_types"], data["dem"]
    depot = nodes["O01"]

    q1_rows: list[dict[str, Any]] = []
    q1_by_service: dict[str, list[dict[str, Any]]] = {}
    safe_rows: list[dict[str, Any]] = []
    for service_id in sorted(k for k in nodes if k.startswith("S")):
        service_boxes = boxes[boxes["服务区编号"] == service_id]
        batches = exact_q1_service(dem, depot, nodes[service_id], service_boxes, types)
        q1_by_service[service_id] = batches
        for type_id, g in types.items():
            safe_rows.append(
                {"service_id": service_id, "type_id": type_id,
                 "safe_payload_kg": max_safe_payload(dem, depot, nodes[service_id], g)}
            )
        for batch_index, batch in enumerate(batches, start=1):
            q1_rows.append(
                {"trip_id": f"Q1-{service_id}-{batch_index:02d}", "service_id": service_id,
                 "type_id": batch["type_id"], "box_ids": ";".join(batch["box_ids"]),
                 "mass_kg": batch["mass_kg"], "volume_m3": batch["volume_m3"],
                 "duration_s": batch["duration_s"], "energy_kwh": batch["energy_kwh"],
                 "return_soc": batch["return_soc"]}
            )
    pd.DataFrame(q1_rows).to_csv(results_dir / "q1_batches.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(safe_rows).to_csv(results_dir / "q1_safe_payload.csv", index=False, encoding="utf-8-sig")

    q2_specs = _build_q2_specs(data, q1_by_service)
    q2_trips, deliveries = _schedule_q2(data, q2_specs)
    q2_trip_rows = [
        {k: v for k, v in trip.items() if k not in ("leg_records", "service_records")}
        for trip in q2_trips
    ]
    for row in q2_trip_rows:
        row["route"] = ";".join(row["route"])
        row["box_ids"] = ";".join(row["box_ids"])
    pd.DataFrame(q2_trip_rows).to_csv(results_dir / "q2_transport_trips.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(deliveries).to_csv(results_dir / "q2_box_deliveries.csv", index=False, encoding="utf-8-sig")

    cover = pd.Series([b for trip in q2_trips for b in trip["box_ids"]]).value_counts()
    hard_late = [x for x in deliveries if x["hard_deadline_s"] is not None and not x["hard_on_time"]]
    q3_trips, relay_missions, communication_rows, q3_summary = _schedule_q3_joint(data, q2_trips)
    q3_trip_rows = []
    for trip in q3_trips:
        row = {k: v for k, v in trip.items() if k not in ("leg_records", "service_records", "completions")}
        row["route"] = ";".join(row["route"])
        row["box_ids"] = ";".join(row["box_ids"])
        q3_trip_rows.append(row)
    relay_rows = []
    for mission in relay_missions:
        row = dict(mission)
        row["served_trip_ids"] = ";".join(row["served_trip_ids"])
        relay_rows.append(row)
    pd.DataFrame(q3_trip_rows).to_csv(results_dir / "q3_transport_trips.csv", index=False, encoding="utf-8-sig")
    q3_delivery_rows = [
        {"trip_id": trip["trip_id"], **completion}
        for trip in q3_trips for completion in trip["completions"]
    ]
    pd.DataFrame(q3_delivery_rows).to_csv(
        results_dir / "q3_box_deliveries.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(relay_rows).to_csv(results_dir / "q3_relay_missions.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(communication_rows).to_csv(results_dir / "q3_communication_segments.csv", index=False, encoding="utf-8-sig")
    q4_rows, q4_summary = _solve_q4_partitions(
        data, q3_trips, relay_missions, communication_rows
    )
    pd.DataFrame(q4_rows).to_csv(results_dir / "q4_partition_resources.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(q4_summary).to_csv(results_dir / "q4_shortage_redundancy.csv", index=False, encoding="utf-8-sig")

    q1_cover = pd.Series(
        [box_id for batches in q1_by_service.values() for batch in batches for box_id in batch["box_ids"]]
    ).value_counts()
    q4_formula_ok = all(
        row["shortfall"] == max(0, row["total_group_need"] - row["inventory"])
        and row["partition_redundancy"] == row["total_group_need"] - row["central_need"]
        for row in q4_summary
    )
    report = {
        "mode": "full",
        "seed": SEED,
        "input_hashes": data["input_hashes"],
        "q1": {"trip_count": len(q1_rows), "energy_kwh": sum(x["energy_kwh"] for x in q1_rows),
               "duration_s": sum(x["duration_s"] for x in q1_rows), "safe_payload_rows": len(safe_rows)},
        "q2": {"trip_count": len(q2_trips), "hard_late_count": len(hard_late),
               "makespan_s": max(x["return_s"] for x in q2_trips),
               "energy_kwh": sum(x["energy_kwh"] for x in q2_trips),
               "wtd": sum(x["priority"] * x["tardiness_s"] / x["expected_s"]
                          for x in deliveries if x["hard_deadline_s"] is None),
               "multi_stop_trips": sum(len(x["route"]) > 1 for x in q2_trips)},
        "q3": q3_summary,
        "q4": {"partition_rows": len(q4_rows), "summary_rows": len(q4_summary),
               "max_shortfall": max(x["shortfall"] for x in q4_summary)},
        "sanity": {"q1_unique_cover": (
                        len(q1_cover) == len(boxes) and bool((q1_cover == 1).all())
                    ),
                   "q2_unique_cover": len(cover) == len(boxes) and bool((cover == 1).all()),
                   "q2_zero_hard_late": len(hard_late) == 0,
                   "q3_zero_hard_late": q3_summary["hard_late_count"] == 0,
                   "q3_zero_continuous_outage": q3_summary["outage_interval_count"] == 0,
                   "q3_zero_grid_outage": q3_summary["grid_outage_count"] == 0,
                   "q4_formulas": q4_formula_ok},
    }
    (results_dir / "full_results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="2026 华为杯 D 题求解")
    parser.add_argument("--mode", choices=["slice", "full"], default="slice")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parent)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    if args.mode == "slice":
        report = run_slice(project_root)
        status = "PASS" if all(report["sanity"].values()) else "FAIL"
        print(json.dumps({"status": status, "sanity": report["sanity"], "q1": report["q1"], "q2": report["q2"]["effective_deadlines_s"], "q3": report["q3"]["continuous_check"]}, ensure_ascii=False, indent=2))
        return 0 if all(report["sanity"].values()) else 2
    report = run_full(project_root)
    status = "PASS" if all(report["sanity"].values()) else "FAIL"
    print(json.dumps({"status": status, **report}, ensure_ascii=False, indent=2))
    return 0 if all(report["sanity"].values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
