from pathlib import Path

import solve_d as solver


def main() -> None:
    root = Path(__file__).resolve().parent
    data = solver.load_inputs(root)
    dem = data["dem"]
    depot = data["nodes"]["O01"]
    service = data["nodes"]["S007"]
    _, terrain, _ = dem.path_elevations(depot.lon, depot.lat, service.lon, service.lat)
    assert abs(float(terrain.max()) - 461.9731750488281) < 1e-6

    report = solver.run_q2_revision(root)
    assert report["sanity"] == {"unique_cover": True, "zero_hard_late": True}
    assert report["selected_score"] < report["baseline_score"]


if __name__ == "__main__":
    main()
