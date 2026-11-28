"""Hybrid answering: GraphRAG for knowledge, the YouBike API for live numbers.

Design rule: live bike counts never pass through the language model. The model gets
station names and distances (static facts); the app shows counts straight from the API
with their update time. So the model cannot invent or misquote a live number.

modes:
  "hybrid"  local search + nearest stations by distance + live cards + tour links
  "hybrid2" graph route: places in the question -> gates -> stations on the campus graph and the
            GraphRAG graph, with computed facts and cited reasons (see graph_route.py)
  "local", "global", "drift", "basic"  plain GraphRAG, for comparison
"""
import csv
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "app"))

import nearest_station as ns  # noqa: E402
from graph_query import context_graph, context_sources, run_query  # noqa: E402

_cache = {}


def _read_csv(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def buildings():
    if "buildings" not in _cache:
        _cache["buildings"] = ns.load_buildings()
    return _cache["buildings"]


def campus_stations():
    if "stations" not in _cache:
        _cache["stations"] = _read_csv(ROOT / "data" / "stations_campus.csv")
    return _cache["stations"]


def tours():
    """360° tour link of each station: data/virtual_tours.csv, else the Tour A panorama taken at
    the station (data/walkway_nodes.csv, rows with a station number)."""
    links = {r["sno"]: {"station_id": r["sno"], "tour_url": r["tour_url"]}
             for r in _read_csv(ROOT / "data" / "walkway_nodes.csv") if r.get("sno") and r.get("tour_url")}
    links.update({t["station_id"]: t for t in _read_csv(ROOT / "data" / "virtual_tours.csv") if t.get("tour_url")})
    return links


def _short(name):
    """'YouBike2.0_NTUST(Back Gate)' -> 'NTUST(Back Gate)'"""
    return re.sub(r"^YouBike\s*2\.0_", "", name or "").strip()


def stations_named_in(text):
    """sno of campus stations whose name appears in a piece of text."""
    found = []
    for s in campus_stations():
        for name in (_short(s["sna"]), _short(s["snaen"])):
            if len(name) >= 4 and name.lower() in text.lower():
                found.append(s["sno"])
                break
    return found


def live_cards(snos, feed, distances=None):
    """Station cards with live numbers from the API feed (None feed -> no numbers)."""
    by_sno = {s["sno"]: s for s in feed} if feed else {}
    info = {s["sno"]: s for s in campus_stations()}
    tour_by_sno = tours()
    cards = []
    for sno in snos:
        live = by_sno.get(sno)
        meta = info.get(sno, {})
        cards.append({
            "sno": sno,
            "name": _short((live or meta).get("snaen") or (live or meta).get("sna", sno)),
            "name_zh": _short((live or meta).get("sna", "")),
            "distance_m": (distances or {}).get(sno),
            "bikes": int(live["sbi"]) if live else None,
            "free_docks": int(live["bemp"]) if live else None,
            "active": (live or {}).get("act") == "1" if live else None,
            "updated": live.get("mday", "") if live else "",
            "tour_url": tour_by_sno.get(sno, {}).get("tour_url", ""),
            "lat": float((live or meta).get("lat") or 0) or None,
            "lng": float((live or meta).get("lng") or 0) or None,
        })
    return cards


def answer(question, mode="hybrid", k=3, root=None, response_type="Multiple Paragraphs", overrides=None,
           live=True, here=None):
    """Return a dict with the answer, sources, recognised place, station cards and timing.

    root: GraphRAG folder to query (default: GRAPHRAG_ROOT, normally graphrag/).
    response_type, overrides: passed to run_query (the evaluation uses them).
    live: False skips the YouBike API call (the evaluation does not need live counts).
    here: the user's location {"lat", "lng", "accuracy"}; only Hybrid v2 uses it.
    """
    if mode == "hybrid2":
        import graph_route  # imported here: graph_route imports this module
        return graph_route.answer(question, root=root, overrides=overrides, live=live, here=here)
    place = ns.find_place(question, buildings())
    result = {"question": question, "mode": mode, "place": place["name"] if place else None,
              "place_coords": (place["lat"], place["lng"]) if place and place["lat"] is not None else None,
              "stations": [], "live_error": None, "notes": []}

    if mode != "hybrid":
        r = run_query(question, mode, root=root, response_type=response_type, overrides=overrides)
        result["context"] = r["context"]
        result.update(answer=r["answer"], sources=context_sources(r["context"]), seconds=r["seconds"],
                      graph_context=context_graph(r["context"]))
        return result

    feed = None
    try:
        feed = ns.fetch_stations() if live else None
    except Exception as exc:  # network down, API changed, ...
        result["live_error"] = f"{type(exc).__name__}: {exc}"

    prompt = question
    distances = {}
    nearest = []
    if place and place["lat"] is None:
        result["notes"].append(f"{place['name']} has no coordinates yet; run scripts/georef.py.")
    elif place:
        candidates = campus_stations()
        for s in candidates:
            d = ns.haversine_m(place["lat"], place["lng"], float(s["lat"]), float(s["lng"]))
            distances[s["sno"]] = round(d)
        nearest = sorted(distances, key=distances.get)[:k]
        if nearest:
            listing = "; ".join(
                f"{_short(next(s['snaen'] or s['sna'] for s in candidates if s['sno'] == sno))} "
                f"(station {sno}, about {distances[sno]} m)" for sno in nearest)
            prompt = (f"{question}\n\nFor reference, the YouBike stations nearest to {place['name']} by "
                      f"straight-line distance are: {listing}. Live bike counts are shown to the user "
                      f"separately, so do not state any bike counts.")

    r = run_query(prompt, "local", root=root, response_type=response_type, overrides=overrides)
    result["context"] = r["context"]
    result.update(answer=r["answer"], sources=context_sources(r["context"]), seconds=r["seconds"],
                  graph_context=context_graph(r["context"]))

    snos = nearest or stations_named_in(r["answer"])[:k]
    result["stations"] = live_cards(snos, feed, distances)
    return result


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "Which station near the library should I use, and how do I recognise it?"
    out = answer(q)
    print(out["answer"])
    print("\nPlace:", out["place"], "| seconds:", round(out["seconds"], 1), "| live error:", out["live_error"])
    for c in out["stations"]:
        print(c)
