"""Download the YouBike feed and keep the stations around campus.

Needs coordinates in data/buildings.csv first (run scripts/georef.py).

Writes:
- data/raw/youbike_<date>.json        the full feed, for reproducibility
- data/stations_campus.csv            active stations within --radius metres of campus
- data/map_youbike_markers.csv        fills sno and api_name for markers that match a
                                      station within --match metres (only empty rows)

Usage: python scripts/fetch_stations.py [--radius 800] [--match 80]
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, HERE)
import nearest_station as ns  # noqa: E402

CAMPUS_CATEGORIES = {"administration", "academic", "public", "dining", "dormitory", "sports", "gate"}


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def write_csv(path, fields, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--radius", type=float, default=800, help="metres from the nearest campus place")
    ap.add_argument("--match", type=float, default=80, help="metres for matching map markers to stations")
    args = ap.parse_args()

    places = [p for p in ns.load_buildings() if p["category"] in CAMPUS_CATEGORIES]
    if not places or places[0]["lat"] is None:
        raise SystemExit("data/buildings.csv has no coordinates yet. Run scripts/georef.py first.")

    raw_text = None
    stub = os.environ.get("YOUBIKE_STUB_FILE")
    if stub:
        with open(stub, encoding="utf-8") as f:
            raw_text = f.read()
    else:
        raw_text = ns.requests.get(ns.API_URL, timeout=30).text
    os.makedirs(os.path.join(ROOT, "data", "raw"), exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M")
    with open(os.path.join(ROOT, "data", "raw", f"youbike_{stamp}.json"), "w", encoding="utf-8") as f:
        f.write(raw_text)
    raw = json.loads(raw_text)
    if isinstance(raw, dict):
        raw = raw.get("retVal") or raw.get("data") or list(raw.values())
    stations = [ns.normalize_station(r) for r in raw]
    print(f"Feed has {len(stations)} stations. First record fields: {sorted(raw[0].keys())}")

    rows = []
    for s in stations:
        if s.get("act") != "1":
            continue
        lat, lng = float(s["lat"]), float(s["lng"])
        dists = sorted((ns.haversine_m(lat, lng, p["lat"], p["lng"]), p["name"]) for p in places)
        if dists[0][0] > args.radius:
            continue
        rows.append({
            "sno": s["sno"], "sna": s.get("sna", ""), "snaen": s.get("snaen", ""),
            "sarea": s.get("sarea", ""), "sareaen": s.get("sareaen", ""),
            "ar": s.get("ar", ""), "aren": s.get("aren", ""),
            "lat": f"{lat:.6f}", "lng": f"{lng:.6f}", "tot": s.get("tot", ""),
            "nearest_place": dists[0][1], "nearest_place_m": round(dists[0][0]),
        })
    rows.sort(key=lambda r: r["nearest_place_m"])
    fields = ["sno", "sna", "snaen", "sarea", "sareaen", "ar", "aren", "lat", "lng", "tot",
              "nearest_place", "nearest_place_m"]
    write_csv(os.path.join(ROOT, "data", "stations_campus.csv"), fields, rows)
    print(f"Kept {len(rows)} active stations within {args.radius:.0f} m of campus -> data/stations_campus.csv")
    for r in rows:
        print(f"  {r['sno']}  {r['nearest_place_m']:>4} m from {r['nearest_place']:<32} {r['snaen'] or r['sna']}")

    mpath = os.path.join(ROOT, "data", "map_youbike_markers.csv")
    mfields, markers = read_csv(mpath)
    # Match each map marker to its nearest station, closest pairs first, one station per marker.
    pairs = []
    for m in markers:
        if not m["lat"]:
            continue
        for r in rows:
            d = ns.haversine_m(float(m["lat"]), float(m["lng"]), float(r["lat"]), float(r["lng"]))
            pairs.append((d, m["marker_id"], r["sno"]))
    used_markers = {m["marker_id"] for m in markers if m["sno"]}
    used_stations = {m["sno"] for m in markers if m["sno"]}
    match = {}
    for d, mid, sno in sorted(pairs):
        if mid in used_markers or sno in used_stations or d > args.match:
            continue
        match[mid] = (sno, d)
        used_markers.add(mid)
        used_stations.add(sno)
    by_sno = {r["sno"]: r for r in rows}
    print("\nMap markers:")
    for m in markers:
        if m["sno"]:
            note = "" if m["sno"] in by_sno else "  <- not among active campus stations, please check"
            print(f"  {m['marker_id']:<14} already set to {m['sno']}{note}")
        elif m["marker_id"] in match:
            sno, d = match[m["marker_id"]]
            r = by_sno[sno]
            m["sno"], m["api_name"] = sno, f"{r['sna']} / {r['snaen']}"
            print(f"  {m['marker_id']:<14} filled with {sno} ({d:.0f} m): {r['snaen'] or r['sna']}")
        else:
            print(f"  {m['marker_id']:<14} no active station within {args.match:.0f} m (it may no longer exist)")
    write_csv(mpath, mfields, markers)


if __name__ == "__main__":
    main()
