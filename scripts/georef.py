"""Turn map pixel positions into latitude and longitude.

The official campus map is a drawing, so every place in data/buildings.csv only has a
pixel position (map_x, map_y). This script fits an affine transform from a few anchor
points whose real coordinates you know, then fills lat and lng for every place.

1. Open data/georef_anchors.csv and fill lat, lng for at least 3 rows (4 or more is
   better, spread over the four corners of campus). Get them in Google Maps: right
   click the spot, click the first line (the coordinates) to copy "lat, lng".
2. Run:  python scripts/georef.py
3. Read the residuals it prints. Below about 15 m is good for a drawn map.

Rows whose coord_source is "verified" (coordinates you measured yourself) or that come
from OpenStreetMap or the API are never overwritten.

Usage: python scripts/georef.py [--data DATA_DIR] [--dry-run]
"""
import argparse
import csv
import math
import os

import numpy as np

KEEP_SOURCES = ("verified", "openstreetmap", "api")


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def write_csv(path, fields, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def metres(lat1, lng1, lat2, lng2):
    """Small-distance approximation, good to well under 1 m inside one campus."""
    k = 111_320.0
    dy = (lat2 - lat1) * k
    dx = (lng2 - lng1) * k * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


def fit(anchors):
    """Least-squares affine fit: [x, y, 1] -> lat and [x, y, 1] -> lng."""
    a = np.array([[float(r["map_x"]), float(r["map_y"]), 1.0] for r in anchors])
    lat = np.array([float(r["lat"]) for r in anchors])
    lng = np.array([float(r["lng"]) for r in anchors])
    c_lat, *_ = np.linalg.lstsq(a, lat, rcond=None)
    c_lng, *_ = np.linalg.lstsq(a, lng, rcond=None)
    return c_lat, c_lng


def apply(c_lat, c_lng, x, y):
    v = np.array([x, y, 1.0])
    return float(v @ c_lat), float(v @ c_lng)


def describe(c_lat, c_lng):
    """Print scale and orientation so obviously wrong anchors stand out."""
    lat0, lng0 = apply(c_lat, c_lng, 1000, 800)
    lat_r, lng_r = apply(c_lat, c_lng, 1100, 800)   # 100 px to the right
    lat_d, lng_d = apply(c_lat, c_lng, 1000, 900)   # 100 px down
    m_right = metres(lat0, lng0, lat_r, lng_r) / 100
    m_down = metres(lat0, lng0, lat_d, lng_d) / 100

    def bearing(lat1, lng1, lat2, lng2):
        dy = lat2 - lat1
        dx = (lng2 - lng1) * math.cos(math.radians(lat1))
        return (math.degrees(math.atan2(dx, dy)) + 360) % 360

    print(f"Scale: {m_right:.2f} m per pixel across, {m_down:.2f} m per pixel down")
    print(f"Map 'right' points to compass bearing {bearing(lat0, lng0, lat_r, lng_r):.0f} deg, "
          f"map 'down' to {bearing(lat0, lng0, lat_d, lng_d):.0f} deg")


def update(path, c_lat, c_lng, label, dry_run):
    fields, rows = read_csv(path)
    changed = 0
    for r in rows:
        src = (r.get("coord_source") or "").lower()
        if r.get("lat") and src.startswith(KEEP_SOURCES):
            continue
        lat, lng = apply(c_lat, c_lng, float(r["map_x"]), float(r["map_y"]))
        r["lat"], r["lng"] = f"{lat:.6f}", f"{lng:.6f}"
        r["coord_source"] = label
        changed += 1
    if not dry_run:
        write_csv(path, fields, rows)
    print(f"{os.path.basename(path)}: {changed} rows {'would be ' if dry_run else ''}updated")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    p = argparse.ArgumentParser()
    p.add_argument("--data", default=os.path.join(here, "..", "data"))
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    _, anchor_rows = read_csv(os.path.join(args.data, "georef_anchors.csv"))
    anchors = [r for r in anchor_rows if r["lat"].strip() and r["lng"].strip()]
    if len(anchors) < 3:
        raise SystemExit(f"Need at least 3 anchors with lat and lng, found {len(anchors)}. "
                         "Fill more rows in data/georef_anchors.csv.")

    c_lat, c_lng = fit(anchors)
    print(f"Fitted on {len(anchors)} anchors")
    errors = []
    for r in anchors:
        lat, lng = apply(c_lat, c_lng, float(r["map_x"]), float(r["map_y"]))
        err = metres(lat, lng, float(r["lat"]), float(r["lng"]))
        errors.append(err)
        print(f"  {r['label']:<24} residual {err:6.1f} m")
    rms = math.sqrt(sum(e * e for e in errors) / len(errors))
    if len(anchors) == 3:
        print("  With exactly 3 anchors the fit is exact, so residuals say nothing. Add a 4th anchor to check accuracy.")
    else:
        print(f"  RMS {rms:.1f} m, max {max(errors):.1f} m")
        if max(errors) > 40:
            print("  WARNING: one anchor is far off. Check it was clicked on the right building.")
    describe(c_lat, c_lng)

    label = f"map_georef ({len(anchors)} anchors, rms {rms:.0f} m)"
    for name in ("buildings.csv", "map_youbike_markers.csv"):
        update(os.path.join(args.data, name), c_lat, c_lng, label, args.dry_run)


if __name__ == "__main__":
    main()
