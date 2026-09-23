#!/usr/bin/env python3
"""Single deterministic reproduction entry for the 2026 Huawei Cup D solution.

AI 辅助说明：本程序及代码是在人工智能工具 OpenAI Codex（GPT-5，
开发机构 OpenAI，版本发布日期 2025-08-07）辅助下完成的。
所有命令、文件和结果均须由参赛者独立复核后使用。
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def run(script: str, *args: str) -> None:
    command = [sys.executable, str(ROOT / script), *args]
    print("RUN", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def record(path: Path) -> dict:
    return {
        "path": str(path.relative_to(ROOT)).replace("/", "\\"),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def write_manifest() -> None:
    data_dir = ROOT / "D题" / "数据" / "无人机应急物资运输基础数据"
    dem = ROOT / "D题" / "数据" / "镇龙乡地理空间数据" / "镇龙乡及周边地理数据" / "数字高程模型数据（DEM）" / "镇龙乡及周边30米DEM.tif"
    inputs = [
        data_dir / "调度中心与服务区.xlsx",
        data_dir / "通信链路参数.xlsx",
        data_dir / "物资需求与配送时限.xlsx",
        data_dir / "运输无人机数据.xlsx",
        data_dir / "中继无人机数据.xlsx",
        dem,
        ROOT / "D题" / "结果提交模板.xlsx",
    ]
    sources = [ROOT / name for name in (
        "solve_d.py", "sensitivity_analysis.py", "make_figures.py",
        "export_submission.py", "reproduce.py", "requirements-lock.txt",
    )]
    result_names = [
        "full_results.json",
        "q1_batches.csv", "q1_safe_payload.csv",
        "q2_transport_trips.csv", "q2_box_deliveries.csv",
        "q3_transport_trips.csv", "q3_box_deliveries.csv",
        "q3_relay_missions.csv", "q3_communication_segments.csv",
        "q4_partition_resources.csv", "q4_shortage_redundancy.csv",
        "sensitivity_q1_reserve.csv", "sensitivity_q1_safe_payload.csv",
        "sensitivity_q2_delay.csv", "sensitivity_q3_margin.csv",
    ]
    outputs = sorted(
        [RESULTS / name for name in result_names]
        + list(FIGURES.glob("*.png"))
        + list(FIGURES.glob("*.svg"))
        + list((FIGURES / "qa").glob("*_qa_gray.png"))
        + [ROOT / "结果提交表_D题.xlsx"],
        key=lambda p: str(p),
    )
    packages = {}
    for name in ("numpy", "pandas", "Pillow", "openpyxl", "matplotlib"):
        packages[name] = importlib.metadata.version(name)
    manifest = {
        "schema_version": 2,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "random_seed": 20260923,
        "reproduce_command": ".venv\\Scripts\\python.exe reproduce.py",
        "pipeline": [
            "solve_d.py --mode full",
            "sensitivity_analysis.py",
            "make_figures.py",
            "export_submission.py",
        ],
        "scope_note": "diagnose_q3.py/search_relay_pair.py/test_*.py are exploratory diagnostics, not required to reproduce the submitted solution",
        "key_parameters": {
            "transport_return_reserve": 0.20,
            "relay_return_reserve": 0.20,
            "p1_grid_step_s": 0.05,
            "full_grid_step_s": 0.5,
            "interval_tolerance_s": 0.1,
        },
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "dependencies": packages,
        },
        "ai_assistance": {
            "tool": "OpenAI Codex",
            "model": "GPT-5",
            "developer": "OpenAI",
            "release_date": "2025-08-07",
        },
        "input_files": [record(p) for p in inputs],
        "source_files": [record(p) for p in sources],
        "output_files": [record(p) for p in outputs],
    }
    (RESULTS / "复现清单.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(RESULTS / "复现清单.json")


def main() -> int:
    run("solve_d.py", "--mode", "full")
    run("sensitivity_analysis.py")
    run("make_figures.py")
    run("export_submission.py")
    write_manifest()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
