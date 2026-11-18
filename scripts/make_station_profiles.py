"""Write one GraphRAG text file per campus YouBike station.

Reads data/stations_campus.csv (from fetch_stations.py), data/buildings.csv (with
coordinates), data/map_youbike_markers.csv, and, when they exist,
data/virtual_tours.csv and data/raw/snapshots.csv.

Writes graphrag/input/station_<sno>.txt. Old station files are removed first, so the
folder always matches the current station list. Live bike counts are never written;
only typical patterns from at least 3 weekdays of snapshots.

Usage: python scripts/make_station_profiles.py [--date YYYY-MM-DD]
"""
import argparse
import csv
import datetime as dt
import glob
import os
import re
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)
import nearest_station as ns  # noqa: E402

CAMPUS = {"administration", "academic", "public", "dining", "dormitory", "sports"}
FEW = 3  # "few bikes" / "few free docks" threshold


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def short(name):
    """'YouBike2.0_NTUST(Back Gate)' -> 'NTUST(Back Gate)'"""
    return re.sub(r"^YouBike\s*2\.0_", "", name or "").strip()


def about(m):
    return f"about {int(round(m / 10.0) * 10)} m"


def hour_ranges(hours):
    """[8, 9, 18] -> ['08:00-10:00', '18:00-19:00']"""
    out, start, prev = [], None, None
    for h in sorted(hours):
        if start is None:
            start = prev = h
        elif h == prev + 1:
            prev = h
        else:
            out.append(f"{start:02d}:00-{prev + 1:02d}:00")
            start = prev = h
    if start is not None:
        out.append(f"{start:02d}:00-{prev + 1:02d}:00")
    return out


def usage_patterns(snapshots):
    """Typical weekday pattern per station from the snapshot log."""
    by_station = defaultdict(lambda: defaultdict(list))
    days = defaultdict(set)
    first, last = None, None
    for r in snapshots:
        try:
            t = dt.datetime.fromisoformat(r["time"])
            bikes, docks = int(float(r["bikes"])), int(float(r["free_docks"]))
        except (ValueError, KeyError, TypeError):
            continue
        first = t if first is None or t < first else first
        last = t if last is None or t > last else last
        if t.weekday() >= 5 or r.get("act") not in ("1", 1):
            continue
        by_station[r["sno"]][t.hour].append((bikes, docks))
        days[r["sno"]].add(t.date())
    result = {}
    for sno, hours in by_station.items():
        if len(days[sno]) < 3:
            continue
        few_bikes = [h for h, v in hours.items() if statistics.median(b for b, _ in v) < FEW]
        few_docks = [h for h, v in hours.items() if statistics.median(d for _, d in v) < FEW]
        n = sum(len(v) for v in hours.values())
        result[sno] = (n, len(days[sno]), first.date(), last.date(), hour_ranges(few_bikes), hour_ranges(few_docks))
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="retrieval date for the Source line (default: newest raw feed file)")
    args = ap.parse_args()

    stations = read_csv(os.path.join(ROOT, "data", "stations_campus.csv"))
    if not stations:
        raise SystemExit("data/stations_campus.csv is missing or empty. Run scripts/fetch_stations.py first.")
    places = [p for p in ns.load_buildings() if p["lat"] is not None]
    campus = [p for p in places if p["category"] in CAMPUS]
    gates = [p for p in places if p["category"] == "gate"]
    neighbours = [p for p in places if p["category"] == "neighbour"]
    markers = {m["sno"]: m for m in read_csv(os.path.join(ROOT, "data", "map_youbike_markers.csv")) if m["sno"]}
    tours = {t["station_id"]: t for t in read_csv(os.path.join(ROOT, "data", "virtual_tours.csv"))}
    patterns = usage_patterns(read_csv(os.path.join(ROOT, "data", "raw", "snapshots.csv")))

    date = args.date
    if not date:
        feeds = sorted(glob.glob(os.path.join(ROOT, "data", "raw", "youbike_*.json")))
        date = (dt.datetime.strptime(os.path.basename(feeds[-1])[8:16], "%Y%m%d").date().isoformat()
                if feeds else dt.date.today().isoformat())

    out_dir = os.path.join(ROOT, "graphrag", "input")
    os.makedirs(out_dir, exist_ok=True)
    for old in glob.glob(os.path.join(out_dir, "station_*.txt")):
        os.remove(old)

    for s in stations:
        lat, lng = float(s["lat"]), float(s["lng"])

        def ranked(group):
            return sorted(((ns.haversine_m(lat, lng, p["lat"], p["lng"]), p) for p in group), key=lambda x: x[0])

        name_en = short(s["snaen"]) or short(s["sna"])
        lines = [
            f"Source: YouBike 2.0 Taipei real-time API (data.gov.tw dataset 137993), station list retrieved {date}. "
            "Distances are straight-line distances computed by the project team from campus map coordinates.",
            "",
            f"YouBike station {s['sno']}: {name_en} ({short(s['sna'])})",
            f"Name in the YouBike system: {s['snaen'] or s['sna']} / {s['sna']}.",
            f"District: {s['sareaen']} ({s['sarea']}). Address: {s['aren']} ({s['ar']}).",
        ]
        if s.get("tot"):
            lines.append(f"Size: {s['tot']} docks.")
        near = ranked(campus)[:3]
        lines.append("Nearest campus places: " + "; ".join(f"{p['name']} ({p['name_zh']}), {about(d)}" for d, p in near) + ".")
        if gates:
            d, g = ranked(gates)[0]
            lines.append(f"Nearest campus gate: {g['name']}, {about(d)}.")
        if neighbours:
            d, n = ranked(neighbours)[0]
            if d <= 200:
                lines.append(f"Nearby landmark outside campus: {n['name']} ({n['name_zh']}), {about(d)}.")
        if s["sno"] in markers:
            m = markers[s["sno"]]
            lines.append(f"On the official campus map this station is marked {m['location'][0].lower() + m['location'][1:]}.")
        if s["sno"] in patterns:
            n, ndays, first, last, few_bikes, few_docks = patterns[s["sno"]]
            parts = []
            if few_bikes:
                parts.append(f"usually has fewer than {FEW} bikes at " + ", ".join(few_bikes))
            if few_docks:
                parts.append(f"usually has fewer than {FEW} free docks for returning a bike at " + ", ".join(few_docks))
            summary = "; it ".join(parts) if parts else f"usually has at least {FEW} bikes and {FEW} free docks"
            lines.append(f"Typical weekday pattern (from {n} snapshots on {ndays} weekdays, {first} to {last}): "
                         f"the station {summary}.")
        if s["sno"] in tours:
            lines.append(f"Virtual tour: an iStaging virtual tour of this station is available at {tours[s['sno']]['tour_url']}.")
        with open(os.path.join(out_dir, f"station_{s['sno']}.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    with_pattern = sum(1 for s in stations if s["sno"] in patterns)
    print(f"Wrote {len(stations)} station files to graphrag/input ({with_pattern} with a usage pattern)")


if __name__ == "__main__":
    main()
