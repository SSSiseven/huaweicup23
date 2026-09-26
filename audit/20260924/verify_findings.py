"""Read-only counterexamples for the baseline solver; no changes to its results.

AI-assisted audit: OpenAI Codex. This is diagnostic code, not a replacement solver.
"""
from pathlib import Path
import json
import math
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import solve_d as s


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    data = s.load_inputs(ROOT)
    dem = data['dem']
    differences = []
    for a in data['nodes'].values():
        for b in data['nodes'].values():
            if a.node_id >= b.node_id:
                continue
            cuts = [0., 1.]
            axes = [((a.lon-dem.lon0)/dem.dx, (b.lon-dem.lon0)/dem.dx),
                    ((dem.lat0-a.lat)/dem.dy, (dem.lat0-b.lat)/dem.dy)]
            for u, v in axes:
                if u == v:
                    continue
                for k in range(math.floor(min(u, v))-1, math.ceil(max(u, v))+1):
                    tau = (k+.5-u)/(v-u)
                    if 0 < tau < 1:
                        cuts.append(tau)
            cuts = sorted(set(cuts))
            # Every open interval lies inside one nearest-neighbour cell.
            ts = [(x+y)/2 for x, y in zip(cuts, cuts[1:])] + [0., 1.]
            exact = max(dem.elevation(a.lon+tau*(b.lon-a.lon), a.lat+tau*(b.lat-a.lat)) for tau in ts)
            sampled = float(max(dem.path_elevations(a.lon, a.lat, b.lon, b.lat)[1]))
            if exact > sampled + 1e-6:
                differences.append({'from': a.node_id, 'to': b.node_id, 'sampled_max_m': sampled,
                                    'traversed_cell_max_m': exact, 'underestimate_m': exact-sampled})
    relay = pd.read_csv(ROOT / 'results/q3_relay_missions.csv')
    comm = pd.read_csv(ROOT / 'results/q3_communication_segments.csv')
    trips = pd.read_csv(ROOT / 'results/q3_transport_trips.csv')
    groups = pd.read_csv(ROOT / 'results/q4_partition_resources.csv')
    relations = []
    for row in relay.itertuples():
        actual = set(comm.loc[comm.relay_mission_id == row.mission_id, 'trip_id'])
        claimed = set(row.served_trip_ids.split(';'))
        if actual != claimed:
            relations.append({'mission': row.mission_id, 'claimed': sorted(claimed), 'actual': sorted(actual)})

    def peak(starts, ends):
        # Releases precede acquisitions at equal times: half-open intervals.
        count = highest = 0
        for _, delta in sorted([(float(v), 1) for v in starts] + [(float(v), -1) for v in ends]):
            count += delta
            highest = max(highest, count)
        return highest

    comparisons = []
    for row in groups.itertuples():
        services = set(row.services.split(';'))
        ids = set(trips.loc[trips.route.map(lambda z: bool(set(z.split(';')) & services)), 'trip_id'])
        old = relay[relay.served_trip_ids.map(lambda z: bool(set(z.split(';')) & ids))]
        actual_ids = set(comm.loc[comm.trip_id.isin(ids), 'relay_mission_id'].dropna())
        new = relay[relay.mission_id.isin(actual_ids)]
        comparison = {'K': row.K, 'group': row.group, 'services': row.services,
                      'extra_missions': sorted(set(old.mission_id)-actual_ids)}
        for label, frame in [('claimed', old), ('actual', new)]:
            comparison[label] = {'missions': frame.mission_id.tolist(),
                                 'relay_uav': peak(frame.start_s, frame.available_s),
                                 'relay_pack': peak(frame.start_s, frame.pack_charge_complete_s),
                                 'relay_workload_h': float((frame.available_s-frame.start_s).sum()/3600)}
        comparisons.append(comparison)
    report = {'scope': 'Current nearest-grid semantics and frozen partition only; no new optimum claimed',
              'node_pairs_checked': 120, 'dem_underestimates': differences,
              'relay_relation_mismatches': relations, 'fixed_group_comparison': comparisons}
    target = Path(__file__).with_name('findings_evidence.json')
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
