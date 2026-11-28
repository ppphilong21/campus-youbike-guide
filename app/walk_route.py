"""Walking routes on the campus walkway graph (the panoramas of the 360° tour).

Nodes are the 13 panoramas of Tour A (data/walkway_nodes.csv), edges are its hotspot links
(data/walkway_edges.csv), weighted by straight-line metres between the two panoramas. A
place is joined to the graph at the panorama that shows it (the `shows` column), else at its
nearest panoramas; a route is the shortest path between the two ends (Dijkstra). Everything here is computed by code: the
language model only puts the route into words.

The graph covers the two photographed routes (Main Gate -> Library -> Back Gate, and
Library -> Lane 155 -> NTU Cancer Center station) and Keelung Road in front of the Main Gate.
A place far from both routes gets a route that ends with a long straight-line step, which is
said in the facts.
"""
import csv
import heapq
import re
from functools import lru_cache

import hybrid

NODES = hybrid.ROOT / "data" / "walkway_nodes.csv"
EDGES = hybrid.ROOT / "data" / "walkway_edges.csv"
SNAP_MAX = 150      # a place farther than this from every panorama is "off the photographed routes"
NEAR_360 = 60       # a panorama within this distance shows the place (the "See it in 360°" button)
SAME_SPOT = 80      # two places closer than this need no route
WALK_M_PER_MIN = 80
PREFER_SHOWN = 40   # metres a route may add to start/end at the panorama that shows the place

ROUTE_WORDS = re.compile(
    r"\bhow (do|can|should) (i|we) (get|go|walk)\b|\bget (from|to)\b|\bwalk(ing)? (from|to|there)\b|\bway (to|from)\b"
    r"|\bdirections?\b|\broute\b|\bfrom\b.+\bto\b|đi từ|đi (đến|tới)|đường (đi )?(từ|đến|tới)|chỉ đường"
    r"|làm (sao|thế nào) để (đi|đến|tới)|怎麼走|怎么走|如何(去|到|走)|從.+到|走到", re.I)
FROM_WORDS = re.compile(r"\bfrom\b|\btừ\b|從|从", re.I)
HERE_WORDS = re.compile(r"\bhere\b|\bmy location\b|\bnear me\b|\bwhere i am\b|chỗ (tôi|mình)|đây|vị trí của tôi"
                        r"|這裡|这里|我這|我这", re.I)


def _read(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@lru_cache(maxsize=1)
def graph():
    """(nodes by id, adjacency {id: [(id, metres)]})."""
    nodes = {}
    for r in _read(NODES):
        if r.get("lat") and r.get("lng"):
            nodes[r["id"]] = dict(r, lat=float(r["lat"]), lng=float(r["lng"]))
    adj = {n: [] for n in nodes}
    for e in _read(EDGES):
        a, b = e["from"], e["to"]
        if a in nodes and b in nodes:
            d = hybrid.ns.haversine_m(nodes[a]["lat"], nodes[a]["lng"], nodes[b]["lat"], nodes[b]["lng"])
            adj[a].append((b, d))
            adj[b].append((a, d))
    return nodes, adj


def dist(a, b):
    return hybrid.ns.haversine_m(a["lat"], a["lng"], b["lat"], b["lng"])


def nearest_nodes(point, k=2):
    nodes, _ = graph()
    return sorted(((dist(point, n), nid) for nid, n in nodes.items()))[:k]


def nearest_panorama(point, within=NEAR_360):
    """The panorama that shows a place, if one is close enough: (node, metres) or None."""
    near = nearest_nodes(point, 1)
    if near and near[0][0] <= within:
        return graph()[0][near[0][1]], round(near[0][0])
    return None


def shown_at(place):
    """Ids of the panoramas whose `shows` column names this place."""
    pid = place.get("id")
    return {nid for nid, n in graph()[0].items() if pid and pid in (n.get("shows") or "").split("|")}


def snap_nodes(place):
    """[(metres, node id)] where a place may join the walkway graph: its 2 nearest panoramas and
    the panoramas that show it."""
    near = nearest_nodes(place)
    seen = {nid for _, nid in near}
    return near + sorted((dist(place, graph()[0][nid]), nid) for nid in shown_at(place) if nid not in seen)


def panorama_for(place):
    """The panorama to open for a place: (node, metres) or None.

    A panorama whose `shows` column names the place comes first (the one the tour was planned
    to show it from); otherwise the nearest panorama within NEAR_360 m.
    """
    pid = place.get("id")
    named = [n for n in graph()[0].values() if pid and pid in (n.get("shows") or "").split("|")]
    if named:
        n = min(named, key=lambda n: dist(place, n))
        return n, round(dist(place, n))
    return nearest_panorama(place)


def station_node(sno):
    return next((n for n in graph()[0].values() if n.get("sno") == str(sno)), None)


def tour_start(place, within=SNAP_MAX):
    """The panorama where the 360° tour should start for a question about this place: the one
    that shows it (panorama_for), else the nearest one within `within` metres. None if too far."""
    pano = panorama_for(place)
    if pano:
        return pano[0]
    near = nearest_nodes(place, 1)
    return graph()[0][near[0][1]] if near and near[0][0] <= within else None


def tour_path(start_id, sno):
    """Panorama ids from start_id to the panorama taken at station `sno` (fewest metres), or None."""
    end = station_node(sno)
    if not end or start_id not in graph()[0]:
        return None
    dists, prev = _dijkstra(start_id)
    if end["id"] not in dists:
        return None
    path = [end["id"]]
    while path[-1] != start_id:
        path.append(prev[path[-1]])
    return path[::-1]


def _dijkstra(src):
    _, adj = graph()
    best, heap = {src: 0.0}, [(0.0, src)]
    prev = {}
    while heap:
        d, u = heapq.heappop(heap)
        if d > best.get(u, float("inf")):
            continue
        for v, w in adj[u]:
            if d + w < best.get(v, float("inf")):
                best[v], prev[v] = d + w, u
                heapq.heappush(heap, (d + w, v))
    return best, prev


def route(origin, dest):
    """Shortest walk from origin to dest (dicts with name, lat, lng).

    Returns None when the walkway graph is empty, else a dict with the legs, the total
    metres and minutes, whether an end is off the photographed routes, and the node ids.
    """
    nodes, _ = graph()
    if not nodes:
        return None
    direct = dist(origin, dest)

    def straight():
        return {"origin": origin["name"], "dest": dest["name"], "nodes": [], "legs": [], "stops": [],
                "metres": round(direct), "minutes": max(1, round(direct / WALK_M_PER_MIN)),
                "direct": True, "off_route": [], "straight_m": round(direct)}

    if direct <= SAME_SPOT:
        return straight()
    best = None
    shown0, shown1 = shown_at(origin), shown_at(dest)
    for d0, s in snap_nodes(origin):
        dists, prev = _dijkstra(s)
        for d1, t in snap_nodes(dest):
            if t not in dists:
                continue
            total = d0 + dists[t] + d1
            # a panorama that shows the place is preferred when it costs at most PREFER_SHOWN m more,
            # so the 360° walk starts (and ends) with a view of the places in the question
            cost = total - PREFER_SHOWN * ((s in shown0) + (t in shown1))
            if best is None or cost < best[0]:
                path, n = [t], t
                while n != s:
                    n = prev[n]
                    path.append(n)
                best = (cost, total, path[::-1], d0, d1)
    if best is None:
        return None
    _, total, path, d0, d1 = best
    if direct < 250 and total > 1.8 * direct:   # the paths make a long detour: walking straight is better
        return dict(straight(), detour=True)
    # stops: (label, node id or None, metres from the previous stop); very short steps are merged
    stops = [(origin["name"], None, 0)]
    prev_pt = origin
    for nid in path:
        stops.append((nodes[nid]["name"], nid, round(dist(prev_pt, nodes[nid]))))
        prev_pt = nodes[nid]
    stops.append((dest["name"], None, round(d1)))
    merged = [stops[0]]
    for label, nid, m in stops[1:]:
        last = merged[-1]
        if m < 5 or label == last[0]:   # the place is at this panorama: keep one stop with the 360° id
            merged[-1] = (last[0], last[1] or nid, last[2] + (m if label == last[0] and m >= 5 else 0))
            continue
        merged.append((label, nid, m))
    legs = [(a[0], b[0], b[2]) for a, b in zip(merged, merged[1:])]
    off = [p["name"] for p, d in ((origin, d0), (dest, d1)) if d > SNAP_MAX]
    return {"origin": origin["name"], "dest": dest["name"], "nodes": path, "legs": legs, "stops": merged,
            "metres": round(total), "minutes": max(1, round(total / WALK_M_PER_MIN)), "direct": False,
            "off_route": off, "straight_m": round(direct)}


def route_fact(r):
    """The route as one fact for the model (Hybrid v2 cites it as Facts (Fn))."""
    if r["direct"]:
        why = ("the photographed campus paths do not go that way" if r.get("detour")
               else "close enough to walk straight there")
        return (f"{r['dest']} is about {r['metres']} m from {r['origin']} in a straight line; {why} "
                f"(about {r['minutes']} min on foot).")
    nodes = graph()[0]
    parts = []
    for i, (label, nid, m) in enumerate(r["stops"]):
        where = f", {nodes[nid]['where']}" if nid and label == nodes[nid]["name"] else ""
        view = f"; 360° view {nid}" if nid else ""
        step = f" (about {m} m)" if i else ""
        parts.append(f"{label}{step}" + (f" [{where.lstrip(', ')}{view}]" if where or view else ""))
    text = (f"Walking route from {r['origin']} to {r['dest']} along the campus paths of the 360° tour: "
            + " -> ".join(parts) + f". In total about {r['metres']} m, about {r['minutes']} min on foot "
            f"(the straight-line distance is about {r['straight_m']} m).")
    if r["off_route"]:
        text += (" " + " and ".join(r["off_route"]) + (" is" if len(r["off_route"]) == 1 else " are")
                 + " off the photographed paths, so that part is a straight-line estimate.")
    return text


def ordered_ends(question, places):
    """(origin, destination) from the places named in a route question.

    The place right after "from" / "từ" / "從" is the origin; otherwise the first one named.
    """
    def first_pos(p):
        hits = [m.start() for _, pat in p["patterns"] for m in [pat.search(question)] if m]
        return min(hits) if hits else 10 ** 6

    ps = sorted(places, key=first_pos)
    if len(ps) < 2:
        return None
    for m in FROM_WORDS.finditer(question):
        after = [p for p in ps if first_pos(p) >= m.end()]
        if after:
            origin = after[0]
            dest = next(p for p in ps if p is not origin)
            return origin, dest
    return ps[0], ps[1]


def is_route_question(question):
    return bool(ROUTE_WORDS.search(question))


def mentions_here(question):
    return bool(HERE_WORDS.search(question))
