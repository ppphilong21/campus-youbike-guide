"""Build the campus walkway graph from the panoramas of the 360° tour (Tour A).

Each panorama is a node; each hotspot link between two panoramas is an edge, so the
tour doubles as a small graph of walking paths. The app uses it to give walking routes
(place -> place, place -> station) and to open the 360° view nearest to a place.

Input (edit here): the panorama list below, with its position on the official campus map
(pixels, the same map as data/buildings.csv), and the hotspot links.
Output: data/walkway_nodes.csv and data/walkway_edges.csv.

Coordinates: map pixels are turned into lat/lng with the same affine fit as
scripts/georef.py (data/georef_anchors.csv). Panoramas at a YouBike station take the
station's own coordinates from data/stations_campus.csv. Once the photos are taken, put
the real coordinates in walkway_nodes.csv with coord_source "verified"; re-running this
script keeps them. Put each panorama's iStaging link in the tour_url column.

Usage: python scripts/make_walkway.py
"""
import csv
import os

import georef

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

# id, name, where to stand, map_x, map_y, YouBike station number (if the panorama is at one)
PANORAMAS = [
    ("A01", "Main Gate", "just inside the Main Gate, on the entrance path", 1140, 1250, ""),
    ("A02", "Main Gate station", "on Keelung Road in front of T1 and RB, by the docks", 785, 1319, "500101024"),
    ("A03", "Library", "on the entrance path in front of the Library, near the Huaxia shuttle stop", 1045, 1160, ""),
    ("A04", "AD, west side", "on the walkway between T4 and the AD lawn", 1020, 1020, ""),
    ("A05", "Central lawn", "in the middle of the lawn between E1 and MA", 1135, 800, ""),
    ("A06", "Path to the Back Gate", "at the north end of the lawn beside the 2nd Student Dormitory", 1225, 620, ""),
    ("A07", "Back Gate (Haoyang side)", "just inside the Back Gate on Alley 68", 1240, 505, ""),
    ("A08", "Back Gate station", "just outside the Back Gate on Alley 68, by the docks", 1360, 470, "500101027"),
    ("A09", "South of T4", "between the Library, the Auditorium and T4", 900, 1080, ""),
    ("A10", "West end of T4", "on the path north of the tennis court", 650, 985, ""),
    ("A11", "By the courts", "on the path between the volleyball and basketball courts", 420, 985, ""),
    ("A12", "Lane 155 entrance", "at the Lane 155 parking lot entrance with the security post beside TR", 205, 1020, ""),
    ("A13", "Cancer Center station", "on Lane 155 opposite the Gymnasium and IA, by the docks", 125, 823, "500101028"),
]
# hotspot links of Tour A (all two-way)
LINKS = [("A01", "A02"), ("A01", "A03"), ("A03", "A04"), ("A04", "A05"), ("A05", "A06"), ("A06", "A07"),
         ("A07", "A08"), ("A03", "A09"), ("A09", "A10"), ("A10", "A11"), ("A11", "A12"), ("A12", "A13")]

FIELDS = ["id", "name", "where", "map_x", "map_y", "lat", "lng", "coord_source", "sno", "tour_url"]


def read(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main():
    nodes_path = os.path.join(DATA, "walkway_nodes.csv")
    old = {r["id"]: r for r in read(nodes_path)}
    _, anchors = georef.read_csv(os.path.join(DATA, "georef_anchors.csv"))
    anchors = [a for a in anchors if a.get("lat") and a.get("lng")]
    c_lat, c_lng = georef.fit(anchors)
    stations = {s["sno"]: s for s in read(os.path.join(DATA, "stations_campus.csv"))}

    rows = []
    for pid, name, where, x, y, sno in PANORAMAS:
        prev = old.get(pid, {})
        row = {"id": pid, "name": name, "where": where, "map_x": x, "map_y": y, "sno": sno,
               "tour_url": prev.get("tour_url", "")}
        if prev.get("coord_source") == "verified":
            row.update(lat=prev["lat"], lng=prev["lng"], coord_source="verified")
        elif sno in stations:
            row.update(lat=stations[sno]["lat"], lng=stations[sno]["lng"], coord_source="api")
        else:
            lat, lng = georef.apply(c_lat, c_lng, x, y)
            row.update(lat=f"{lat:.6f}", lng=f"{lng:.6f}", coord_source="map")
        rows.append(row)
    georef.write_csv(nodes_path, FIELDS, rows)

    with open(os.path.join(DATA, "walkway_edges.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["from", "to"])
        w.writerows(LINKS)
    print(f"{len(rows)} panoramas -> data/walkway_nodes.csv, {len(LINKS)} links -> data/walkway_edges.csv")


if __name__ == "__main__":
    main()
