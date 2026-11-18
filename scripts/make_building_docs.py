"""Write the campus text files for GraphRAG from the campus CSVs.

Reads data/buildings.csv, data/campus_units.csv and data/map_youbike_markers.csv and
writes one text file per doc_group into graphrag/input/. Run it again after editing
the CSVs; it overwrites only the files it generates.

Usage: python scripts/make_building_docs.py [--date YYYY-MM-DD]
"""
import argparse
import csv
import os
from collections import OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")

SOURCE = ("Source: Official Taiwan Tech campus layout map (國立臺灣科技大學校園平面配置圖, "
          "Layout of Taiwan Tech), read by the project team on {date}.")

CATEGORY = {
    "administration": "administration building",
    "academic": "academic building",
    "public": "public facility",
    "dining": "cafeteria",
    "dormitory": "dormitory",
    "sports": "sports facility",
    "gate": "campus gate",
    "parking": "parking",
    "transport": "transport point",
    "security": "security post",
    "service": "campus service",
    "research": "research center",
    "neighbour": "neighbouring place outside the campus",
}

TITLES = {
    "dining_and_post_office": "Cafeterias and the Post Office at Taiwan Tech",
    "dormitories": "Student and faculty dormitories at Taiwan Tech",
    "sports_grounds": "Sports grounds at Taiwan Tech",
    "gates_parking_and_services": "Gates, parking, shuttle buses and services at Taiwan Tech",
    "campus_surroundings": "Taiwan Tech campus surroundings and YouBike stations on the official map",
}

SURROUNDINGS_INTRO = (
    "National Taiwan University of Science and Technology (Taiwan Tech, NTUST) is at No. 43, Keelung Road "
    "Section 4, Da'an District, Taipei 10607. On the official campus map the campus is bounded by four roads. "
    "Keelung Road Section 4 runs along the front of campus, where the Main Gate is. Lane 155 of Keelung Road "
    "Section 3 runs along the side with the Gymnasium, IA and TR buildings. Alley 68 of Lane 41, Keelung Road "
    "Section 4 runs along the back of campus, where the Back Gate and the student dormitories are. Lane 41 and "
    "Lane 73 of Keelung Road Section 4 run along the side with the EE, T2, E2 and IB buildings. Along Keelung "
    "Road, the Lane 155 end leads towards Keelung and the Lane 73 end leads towards Gongguan."
)

YOUBIKE_INTRO = (
    "The official campus map marks {n} YouBike stations around the campus. The map may be older than the "
    "current station network, so the station list, station numbers and live bike counts come from the "
    "YouBike API, not from this file."
)


def read(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def place_block(p, units):
    title = p["name"] + (f" ({p['name_zh']})" if p["name_zh"] else "")
    lines = [title]
    facts = []
    if p["map_no"]:
        facts.append(f"number {p['map_no']} on the campus map")
    if p["code"]:
        facts.append(f"building code {p['code']}")
    kind = CATEGORY.get(p["category"], p["category"])
    lines.append(f"Type: {kind}" + (f", {', '.join(facts)}." if facts else "."))
    lines.append(f"Location: {p['description']}")
    if units:
        lines.append(f"Units in {p['name']}:")
        lines += [f"- {u['unit_en']} ({u['unit_zh']})" for u in units]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-11-15")
    args = ap.parse_args()

    places = read(os.path.join(ROOT, "data", "buildings.csv"))
    units = read(os.path.join(ROOT, "data", "campus_units.csv"))
    markers = read(os.path.join(ROOT, "data", "map_youbike_markers.csv"))
    out_dir = os.path.join(ROOT, "graphrag", "input")
    os.makedirs(out_dir, exist_ok=True)

    units_by_building = defaultdict(list)
    for u in units:
        units_by_building[u["building_id"]].append(u)

    groups = OrderedDict()
    for p in places:
        groups.setdefault(p["doc_group"], []).append(p)

    written = []
    for group, members in groups.items():
        parts = [SOURCE.format(date=args.date), ""]
        if group in TITLES:
            parts += [TITLES[group], ""]
        if group == "campus_surroundings":
            parts += [SURROUNDINGS_INTRO, ""]
        for p in members:
            parts += [place_block(p, units_by_building.get(p["id"], [])), ""]
        if group == "campus_surroundings":
            parts += [YOUBIKE_INTRO.format(n=len(markers)), ""]
            for m in markers:
                name = f", named {m['api_name']}" if m["api_name"] else ""
                if m["sno"]:
                    name += f" (station number {m['sno']})"
                parts.append(f"- {m['map_label']} station: {m['location']} ({m['road']}){name}. "
                             f"Nearby on the map: {m['near_places'].replace(';', ',')}.")
            parts.append("")
        path = os.path.join(out_dir, f"{group}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(parts).rstrip() + "\n")
        written.append(path)

    print(f"Wrote {len(written)} files to {os.path.relpath(out_dir, ROOT)}")
    for path in written:
        print("  ", os.path.basename(path))


if __name__ == "__main__":
    main()
