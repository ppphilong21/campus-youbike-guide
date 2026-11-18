"""Find the YouBike stations nearest to a campus place mentioned in a question.

No model training and no Google Maps API are needed:
- station coordinates come from the YouBike 2.0 Taipei API (lat/lng, or latitude/longitude
  in newer versions of the feed; normalize_station() accepts both)
- place coordinates come from data/buildings.csv (filled by scripts/georef.py)
- departments and offices in data/campus_units.csv are mapped to their building,
  so "near the CSIE department" resolves to the T4 building
- distance is the straight-line (haversine) distance in metres

Alias matching rules:
- Chinese aliases match anywhere in the question (圖書館 in 圖書館附近).
- Latin-script aliases (English, Vietnamese, codes like IB or T4) must match as whole
  words, so "TR" does not match inside "station" and "AD" not inside "road".
- If several aliases match, the longest one wins ("T2 Cafeteria" beats "T2").
"""
import csv
import math
import os
import re

import requests

API_URL = "https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
CJK = re.compile(r"[㐀-鿿]")


def haversine_m(lat1, lng1, lat2, lng2):
    """Straight-line distance in metres between two coordinates."""
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _pattern(alias):
    if CJK.search(alias):
        return re.compile(re.escape(alias))
    return re.compile(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", re.IGNORECASE)


def _split(text):
    return [a.strip() for a in (text or "").split("|") if a.strip()]


def load_buildings(path=None, units_path=None):
    """Read campus places, optionally adding department and office names as aliases.

    Places without coordinates are kept (lat and lng are None) so that they can still
    be recognised in a question; nearest_stations() explains what to do for them.
    """
    path = path or os.path.join(DATA, "buildings.csv")
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    by_id = {}
    for row in rows:
        row["lat"] = float(row["lat"]) if row.get("lat") else None
        row["lng"] = float(row["lng"]) if row.get("lng") else None
        row["alias_list"] = _split(row.get("aliases")) + [row["name"]]
        if row.get("name_zh"):
            row["alias_list"].append(row["name_zh"])
        by_id[row["id"]] = row

    if units_path is None:
        default_units = os.path.join(os.path.dirname(path), "campus_units.csv")
        units_path = default_units if os.path.exists(default_units) else None
    if units_path:
        with open(units_path, encoding="utf-8") as f:
            for unit in csv.DictReader(f):
                building = by_id.get(unit["building_id"])
                if building:
                    building["alias_list"] += [unit["unit_en"], unit["unit_zh"]] + _split(unit.get("aliases"))

    for row in rows:
        unique = list(dict.fromkeys(a for a in row["alias_list"] if a))
        row["patterns"] = [(len(a), _pattern(a)) for a in unique]
    return rows


def find_place(question, buildings):
    """Return the place whose alias appears in the question, or None.

    None means no known place was mentioned, so the app should ask the user which
    building they mean.
    """
    best, best_len = None, 0
    for b in buildings:
        for length, pat in b["patterns"]:
            if length > best_len and pat.search(question):
                best, best_len = b, length
    return best


# The Taipei feed has used two sets of field names over time. Each entry lists the
# name used here first, then the alternatives found in the raw feed.
FIELD_ALIASES = {
    "lat": ("lat", "latitude"),
    "lng": ("lng", "longitude"),
    "tot": ("tot", "total"),
    "sbi": ("sbi", "available_rent_bikes"),
    "bemp": ("bemp", "available_return_bikes"),
    "mday": ("mday", "updateTime", "srcUpdateTime", "infoTime"),
}


def normalize_station(raw):
    """Return a station record with the same field names whatever the feed uses."""
    s = dict(raw)
    for key, names in FIELD_ALIASES.items():
        for name in names:
            if raw.get(name) not in (None, ""):
                s[key] = raw[name]
                break
    s["act"] = str(raw.get("act", "")).strip()
    return s


def fetch_stations():
    """Get the current status of all Taipei YouBike stations, with normalised field names.

    For offline tests only: set YOUBIKE_STUB_FILE to a saved JSON file of the feed.
    """
    stub = os.environ.get("YOUBIKE_STUB_FILE")
    if stub:
        import json
        with open(stub, encoding="utf-8") as f:
            raw = json.load(f)
    else:
        raw = requests.get(API_URL, timeout=15).json()
    if isinstance(raw, dict):  # some mirrors wrap the list
        raw = raw.get("retVal") or raw.get("data") or list(raw.values())
    return [normalize_station(r) for r in raw]


def nearest_stations(place, stations, k=3, min_bikes=0):
    """Rank active stations by distance to the place, keeping those with enough bikes."""
    if place["lat"] is None:
        raise ValueError(f"{place['name']} has no coordinates yet. Fill data/georef_anchors.csv "
                         "and run scripts/georef.py.")
    results = []
    for raw in stations:
        s = normalize_station(raw)
        if s.get("act") != "1":
            continue
        if int(s.get("sbi", 0)) < min_bikes:
            continue
        d = haversine_m(place["lat"], place["lng"], float(s["lat"]), float(s["lng"]))
        results.append({
            "sno": s["sno"],
            "name": s.get("snaen") or s["sna"],
            "name_zh": s["sna"],
            "distance_m": round(d),
            "bikes": int(s["sbi"]),
            "free_docks": int(s["bemp"]),
            "updated": s.get("mday", ""),
        })
    return sorted(results, key=lambda r: r["distance_m"])[:k]


if __name__ == "__main__":
    buildings = load_buildings()
    question = "Which station near the library should I use at 8 am?"
    place = find_place(question, buildings)
    if place is None:
        print("No known campus place found in the question. Ask the user which building they mean.")
    else:
        print(f"Place found: {place['name']} ({place['name_zh']})")
        for station in nearest_stations(place, fetch_stations(), k=3, min_bikes=1):
            print(station)
