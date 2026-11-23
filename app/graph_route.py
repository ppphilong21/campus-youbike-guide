"""Hybrid v2 ("graph route"): station advice that follows paths on the campus graph.

Hybrid (v1) adds the three nearest stations to the question and runs GraphRAG Local search.
The evaluation showed two weaknesses: the station list changes what Local search retrieves
(questions F10, L02), and the answer can only rank stations by straight-line distance.

Hybrid v2 starts from the places named in the question and uses two graphs:

1. Campus layer, built by code from the data files (exact, no model): unit -in-> building,
   place -nearest gate-> gate, place -near (m)-> station, station -nearest gate-> gate,
   station -landmark-> place, station -usual weekday pattern-> hours. A time in the question
   is checked against each station's usual pattern.
2. The GraphRAG knowledge graph: places, gates and candidate stations are linked to their
   entities (entity resolution by aliases and station numbers). Paths of up to three steps
   between them, and their neighbours of route-relevant types from the schema (gates, roads,
   landmarks, stops, parking, buildings, ...), are kept; hub entities such as YOUBIKE are
   skipped. The source chunks behind them, and the documents of the places and stations,
   are added.

The model gets the computed facts, the relationship triples and the text, and must cite
them. Live bike counts still never reach the model; the app shows them in the cards.
"""
import csv
import datetime as dt
import functools
import os
import re
import statistics
import time
from pathlib import Path

import requests

import hybrid
import kg_view
from graph_query import GRAPHRAG_ROOT, _merge

SNAPSHOTS = hybrid.ROOT / "data" / "raw" / "snapshots.csv"   # written by scripts/snapshot.py
MIN_SNAPSHOTS, MIN_DAYS = 3, 2   # fewer than this in an hour: "too few snapshots to say"

ROUTE_TYPES = {"GATE", "ROAD", "LANDMARK", "BUS_STOP", "PARKING", "BUILDING", "FACILITY", "YOUBIKE_STATION",
               "DEPARTMENT", "OFFICE"}
NEVER_HUB = {"GATE", "ROAD", "YOUBIKE_STATION", "BUILDING"}
K_STATIONS = 4      # candidate stations given to the model (the nearest one plus backups)
MAX_RELS = 24       # relationship triples in the context
MAX_CHUNKS = 6      # source chunks in the context
MAX_CHARS = 9000    # about 2,300 tokens of source text
CJK = re.compile(r"[㐀-鿿]")

STATION_WORDS = re.compile(r"station|youbike|u-?bike|\bbikes?\b|\brent|\breturn|dock|trạm|\bxe\b|站|車", re.I)
RETURN_WORDS = re.compile(r"\breturn|drop (it )?off|park the bike|free docks?|trả xe|還車", re.I)


# ---------------------------------------------------------------- question parsing

def find_places(question, buildings, limit=3):
    """Places named in the question, longest alias first, without overlapping matches."""
    matches = []
    for b in buildings:
        for length, pat in b["patterns"]:
            for m in pat.finditer(question):
                matches.append((m.start(), m.end(), length, b))
    matches.sort(key=lambda m: -m[2])
    taken, out = [], []
    for start, end, _, b in matches:
        if any(start < e and s < end for s, e in taken) or any(b is o for o in out):
            continue
        taken.append((start, end))
        out.append(b)
        if len(out) == limit:
            break
    return out


def parse_hour(question):
    """'21:30' -> 21.5, '5:30 pm' -> 17.5, 'around 3 pm' -> 15, '9 giờ tối' -> 21, '晚上9點' -> 21."""
    q = question.lower()
    m = re.search(r"(?<![\d.])(\d{1,2}):(\d{2})\s*(a\.?m\.?|p\.?m\.?)?", q)
    if not m:
        m = re.search(r"(?<![\d.])(\d{1,2})()\s*(a\.?m\.?|p\.?m\.?)", q)
    if m:
        h, mins, ampm = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").replace(".", "")
        if ampm == "pm" and h < 12:
            h += 12
        if ampm == "am" and h == 12:
            h = 0
        return h + mins / 60 if h < 24 else None
    m = re.search(r"(\d{1,2})\s*(?:giờ|h)\s*(sáng|trưa|chiều|tối|đêm)?", q)
    if m:
        h = int(m.group(1))
        if m.group(2) in ("chiều", "tối", "đêm") and h < 12:
            h += 12
        return h if h < 24 else None
    m = re.search(r"(上午|中午|下午|晚上)?\s*(\d{1,2})\s*[點点]", question)
    if m:
        h = int(m.group(2))
        if m.group(1) in ("下午", "晚上") and h < 12:
            h += 12
        return h if h < 24 else None
    return None


def clock(hour):
    return f"{int(hour):02d}:{round((hour % 1) * 60):02d}"


# ---------------------------------------------------------------- campus layer

def _ranges(text):
    return [(int(a), int(b)) for a, b in re.findall(r"(\d{1,2}):00\s*-\s*(\d{1,2}):00", text or "")]


@functools.lru_cache(maxsize=64)
def station_profile(root, sno):
    """Facts from graphrag/input/station_<sno>.txt (written by scripts/make_station_profiles.py)."""
    path = Path(root) / "input" / f"station_{sno}.txt"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    gate = re.search(r"campus gate nearest to .*? is the (.+?), about (\d+) m", text)
    landmark = re.search(r"landmark outside campus near .*?: (.+?), about (\d+) m", text)
    marked = re.search(r"On the official campus map, .*? is marked (.+?)\.?\s*$", text, re.M)
    pattern = re.search(r"Typical weekday pattern[^:]*:\s*(.+?)\s*$", text, re.M)
    pat = pattern.group(1) if pattern else ""
    bikes = re.search(r"fewer than 3 bikes at ([0-9:,\- ]+)", pat)
    docks = re.search(r"fewer than 3 free docks for returning a bike at ([0-9:,\- ]+)", pat)
    return {
        "gate": (gate.group(1), int(gate.group(2))) if gate else None,
        "landmark": (landmark.group(1), int(landmark.group(2))) if landmark else None,
        "marked": marked.group(1) if marked else "",
        "pattern": pat.rstrip("."),
        "short_bikes": _ranges(bikes.group(1)) if bikes else [],
        "short_docks": _ranges(docks.group(1)) if docks else [],
        "file": f"station_{sno}" if text else "",
    }


@functools.lru_cache(maxsize=2)
def _snapshots(path, mtime):
    """Weekday samples per station and hour: {sno: {hour: [(date, bikes, docks), ...]}}."""
    by = {}
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            try:
                t = dt.datetime.fromisoformat(r["time"])
                bikes, docks = int(float(r["bikes"])), int(float(r["free_docks"]))
            except (ValueError, KeyError, TypeError):
                continue
            if t.weekday() >= 5 or str(r.get("act", "1")) != "1":
                continue
            by.setdefault(str(r["sno"]), {}).setdefault(t.hour, []).append((t.date(), bikes, docks))
    return by


def snapshots():
    """Read when a question is asked, so new snapshots count without re-indexing."""
    return _snapshots(str(SNAPSHOTS), SNAPSHOTS.stat().st_mtime) if SNAPSHOTS.exists() else {}


def _span(h):
    return f"{h:02d}:00-{(h + 1) % 24:02d}:00"


def _hours_text(hours):
    """[0, 14, 15, 16, 21, 22] -> '00:00-01:00, 14:00-17:00, 21:00-23:00'."""
    out, start, prev = [], None, None
    for h in sorted(hours):
        if start is not None and h == prev + 1:
            prev = h
            continue
        if start is not None:
            out.append(f"{start:02d}:00-{(prev + 1) % 24:02d}:00")
        start = prev = h
    if start is not None:
        out.append(f"{start:02d}:00-{(prev + 1) % 24:02d}:00")
    return ", ".join(out)


def _enough(samples):
    return len(samples) >= MIN_SNAPSHOTS and len({d for d, _, _ in samples}) >= MIN_DAYS


def _sampled_hours(enough_only):
    log = snapshots()
    return {h for hours in log.values() for h, v in hours.items() if not enough_only or _enough(v)}


def coverage_fact():
    """What the snapshot log covers, so the model does not read unsampled hours as quiet."""
    log = snapshots()
    samples = {(d, h) for hours in log.values() for h, v in hours.items() for d, _, _ in v}
    if not samples:
        return ""
    days = sorted({d for d, _ in samples})
    enough = _sampled_hours(True)
    return (f"The bike patterns come from snapshots of the stations on {len(days)} weekdays "
            f"({days[0]:%d %b} to {days[-1]:%d %b %Y}). Only these hours have enough snapshots "
            f"(at least {MIN_SNAPSHOTS} on {MIN_DAYS} days) to say anything: {_hours_text(enough) or 'none'}. "
            f"Nothing is known about the other hours.")


def _n(x, word):
    return f"{x:g} {word}" if x == 1 else f"{x:g} {word}s"


def hour_fact(name, sno, hour, returning):
    """What the snapshots say about one station in the hour asked, with the sample size."""
    h = int(hour) % 24
    what = "free docks" if returning else "bikes"
    samples = snapshots().get(str(sno), {}).get(h, [])
    if not samples:
        return f"No weekday snapshots of {name} station were taken between {_span(h)}, so how many {what} it has then is not known."
    days = sorted({d for d, _, _ in samples})
    med = statistics.median(dk if returning else b for _, b, dk in samples)
    text = (f"Between {_span(h)} on weekdays, {_n(len(samples), 'snapshot')} of {name} station "
            f"on {_n(len(days), 'day')} ({', '.join(f'{d:%d %b}' for d in days)}) had a median of "
            + (_n(med, "free dock") if returning else _n(med, "bike")))
    if not _enough(samples):
        return text + ": too few snapshots to say what is usual."
    return text + (f": in these snapshots it was often short of {what} (fewer than 3)." if med < 3
                   else f": in these snapshots it was not short of {what}.")


def pattern_fact(name, sno):
    """Hours with a median under 3 bikes or docks, counting only hours with enough snapshots."""
    ok = {h: v for h, v in snapshots().get(str(sno), {}).items() if _enough(v)}
    if not ok:
        return ""
    few_bikes = [h for h, v in ok.items() if statistics.median(b for _, b, _ in v) < 3]
    few_docks = [h for h, v in ok.items() if statistics.median(d for _, _, d in v) < 3]
    parts = ([f"bikes at {_hours_text(few_bikes)}"] if few_bikes else []) + \
            ([f"free docks at {_hours_text(few_docks)}"] if few_docks else [])
    if not parts:
        return f"In the weekday snapshots it was not short of bikes or free docks in any sampled hour."
    return f"In the weekday snapshots it was often short (fewer than 3) of " + " and of ".join(parts) + "."


def nearest_gate(place, gates):
    if place.get("lat") is None or not gates:
        return None
    return min(((g, round(hybrid.ns.haversine_m(place["lat"], place["lng"], g["lat"], g["lng"]))) for g in gates),
               key=lambda x: x[1])


def campus_facts(root, places, cands, hour, returning):
    """Facts computed by code (F1, F2, ...) and the campus-layer edges for the drawing."""
    gates = [b for b in hybrid.buildings() if b.get("category") == "gate" and b.get("lat") is not None]
    facts, edges = [], []
    place = places[0]
    pg = nearest_gate(place, gates) if place.get("category") not in ("gate", "neighbour") else None
    if pg:
        facts.append(f"The nearest campus gate to {place['name']} is the {pg[0]['name']}, about {pg[1]} m.")
        edges.append((place["name"], pg[0]["name"], f"nearest gate, about {pg[1]} m"))
    for other in places[1:]:
        if other.get("lat") is not None and place.get("lat") is not None:
            d = round(hybrid.ns.haversine_m(place["lat"], place["lng"], other["lat"], other["lng"]))
            facts.append(f"{other['name']} is about {d} m from {place['name']}.")
    for i, c in enumerate(cands):
        prof = station_profile(str(root), c["sno"])
        name = c["name"]
        parts = [f"{name} station is about {c['distance_m']} m from {place['name']} in a straight line "
                 f"({'the nearest' if i == 0 else 'number ' + str(i + 1) + ' by distance'})."]
        if prof["gate"]:
            same = pg and prof["gate"][0] == pg[0]["name"]
            parts.append(f"Its nearest campus gate is the {prof['gate'][0]}, about {prof['gate'][1]} m"
                         + (f", the same gate that is nearest to {place['name']}." if same else "."))
            edges.append((name + " station", prof["gate"][0], f"nearest gate, about {prof['gate'][1]} m"))
        if prof["marked"]:
            parts.append(f"On the campus map it is marked {prof['marked']}.")
        if prof["landmark"]:
            parts.append(f"Landmark near it: {prof['landmark'][0]}, about {prof['landmark'][1]} m.")
        if not snapshots():                     # no log (fresh clone): fall back to the indexed profile text
            if prof["pattern"]:
                parts.append(f"Weekday pattern in the station file: {prof['pattern']}.")
        elif hour is not None:
            parts.append(hour_fact(name, c["sno"], hour, returning))
        else:
            parts.append(pattern_fact(name, c["sno"]))
        facts.append(" ".join(p for p in parts if p))
        edges.append((place["name"], name + " station", f"about {c['distance_m']} m"))
    if len(cands) > 1 and coverage_fact():
        facts.append(coverage_fact())
    return facts, edges


# ---------------------------------------------------------------- knowledge graph layer

def _norm(title):
    t = str(title or "").upper()
    t = re.sub(r"YOUBIKE\s*2[._ ]?0E?", " ", t)
    t = re.sub(r"[^A-Z0-9㐀-鿿]+", " ", t)
    t = re.sub(r"\bSTATION\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()


@functools.lru_cache(maxsize=2)
def _kg(root, mtime):
    """The GraphRAG index as a networkx graph plus lookups for entities and text chunks."""
    import networkx as nx
    import pandas as pd

    g = kg_view.load_graph(root)
    if g is None:
        return None
    out = Path(root) / "output"
    ents, rels = g["entities"], g["relationships"]
    G = nx.Graph()
    for r in rels.to_dict("records"):
        s, t = r["source"], r["target"]
        units = list(r["text_unit_ids"]) if r.get("text_unit_ids") is not None else []
        if G.has_edge(s, t):
            G[s][t]["units"] += units
            continue
        G.add_edge(s, t, rid=int(r["human_readable_id"]), desc=str(r["description"] or ""),
                   weight=float(r.get("weight") or 1), units=units)
    types = dict(zip(ents["title"], ents["type"]))
    degree = dict(zip(ents["title"], ents["degree"].fillna(0).astype(int)))
    cut = max(15, int(ents["degree"].quantile(0.95))) if len(ents) else 15
    hubs = {t for t, d in degree.items() if d >= cut and types.get(t) not in NEVER_HUB}
    # generic nodes that join everything to everything: "YOUBIKE 2.0 STATION", districts
    hubs |= {t for t in ents["title"] if _norm(t) in ("", "YOUBIKE", "YOUBIKE 1 0") or types.get(t) == "DISTRICT"}
    ent_units = {t: (list(u) if u is not None else []) for t, u in zip(ents["title"], ents["text_unit_ids"])}
    units = pd.read_parquet(out / "text_units.parquet", columns=["id", "human_readable_id", "text", "document_id"])
    docs = pd.read_parquet(out / "documents.parquet", columns=["id", "title"])
    doc_title = {d: Path(str(t)).stem for d, t in zip(docs["id"], docs["title"])}
    unit = {u: (int(h), str(x), doc_title.get(d, "")) for u, h, x, d in
            zip(units["id"], units["human_readable_id"], units["text"], units["document_id"])}
    doc_units = {}
    for u, (_, _, d) in unit.items():
        doc_units.setdefault(d, []).append(u)
    index = {}
    for t in ents["title"]:
        index.setdefault(_norm(t), []).append(t)
    desc = dict(zip(ents["title"], ents["description"].astype(str)))
    return {"g": g, "G": G, "types": types, "degree": degree, "hubs": hubs, "ent_units": ent_units, "unit": unit,
            "doc_units": doc_units, "index": index, "desc": desc}


def kg_for(root):
    f = Path(root) / "output" / "entities.parquet"
    return _kg(str(root), f.stat().st_mtime if f.exists() else 0)


def link_place(kg, place):
    """Entities for a campus place: exact alias matches, also with ' BUILDING' added."""
    found = []
    own = [a.strip() for a in str(place.get("aliases") or "").split("|") if a.strip()]
    for alias in own + [place.get("name", ""), place.get("code", "")]:  # not the unit names
        n = _norm(alias)
        if not n or CJK.search(n):
            continue
        for key in (n, n + " BUILDING"):
            for t in kg["index"].get(key, []):
                if t not in found:
                    found.append(t)
    return sorted(found, key=lambda t: -kg["degree"].get(t, 0))[:3]


def link_station(kg, card):
    n = _norm(card["name"])
    found = [t for key, ts in kg["index"].items() if key == n or key.startswith(n + " ") for t in ts]
    found += [t for t, d in kg["desc"].items() if card["sno"] in d and kg["types"].get(t) == "YOUBIKE_STATION"]
    return sorted(dict.fromkeys(found), key=lambda t: -kg["degree"].get(t, 0))[:3]


def graph_context(kg, place_titles, gate_titles, station_titles, doc_names):
    """Relationship triples on paths between the anchors and around them, and their text chunks."""
    import networkx as nx

    G, hubs, types = kg["G"], kg["hubs"], kg["types"]
    anchors = [t for t in dict.fromkeys(place_titles + gate_titles + station_titles) if t in G]
    H = G.subgraph([n for n in G if n not in hubs or n in anchors])
    picked = []

    def add(s, t):
        key = frozenset((s, t))
        if s != t and H.has_edge(s, t) and key not in {frozenset(p) for p in picked}:
            picked.append((s, t))

    pairs = [(p, s) for p in place_titles[:2] for s in station_titles]
    pairs += [(p, g) for p in place_titles[:2] for g in gate_titles] + [(g, s) for g in gate_titles for s in station_titles]
    pairs += [(a, b) for i, a in enumerate(place_titles) for b in place_titles[i + 1:]]
    for a, b in pairs:
        if a in H and b in H and a != b:
            try:
                path = nx.shortest_path(H, a, b)
            except nx.NetworkXNoPath:
                continue
            if len(path) - 1 <= 3:
                for s, t in zip(path, path[1:]):
                    add(s, t)
    for a in anchors:
        near = sorted((n for n in H.neighbors(a) if types.get(n) in ROUTE_TYPES),
                      key=lambda n: -H[a][n]["weight"])[:3]
        for n in near:
            add(a, n)
    picked = picked[:MAX_RELS]

    # text: documents of the places and stations first, then chunks behind the picked edges
    order, seen = [], set()
    for d in doc_names:
        for u in kg["doc_units"].get(d, []):
            if u not in seen:
                seen.add(u)
                order.append(u)
    counts = {}
    for s, t in picked:
        for u in H[s][t]["units"]:
            counts[u] = counts.get(u, 0) + 1
    for t in anchors:
        for u in kg["ent_units"].get(t, []):
            counts[u] = counts.get(u, 0) + 0.5
    order += [u for u in sorted(counts, key=lambda u: -counts[u]) if u not in seen]
    chunks, size = [], 0
    for u in order:
        if u not in kg["unit"] or len(chunks) >= MAX_CHUNKS:
            continue
        hid, text, doc = kg["unit"][u]
        if size + len(text) > MAX_CHARS and chunks:
            continue
        chunks.append({"id": str(hid), "text": text, "doc": doc})
        size += len(text)
    rels = [{"id": str(H[s][t]["rid"]), "source": s, "target": t, "description": _desc(H[s][t]["desc"])}
            for s, t in picked]
    entities = list(dict.fromkeys(anchors + [x for p in picked for x in p]))
    return {"relationships": rels, "sources": chunks, "entities": entities}


def _desc(text, n=220):
    """Relationship descriptions can be a list of sentences; keep the first one or two."""
    t = str(text or "")
    if t.startswith("["):
        t = " ".join(re.findall(r'"([^"]+)"', t)[:2]) or t
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"


# ---------------------------------------------------------------- answer

SYSTEM = """You are Campus YouBike Guide, a helper for students at National Taiwan University of Science and Technology (Taiwan Tech).

Answer the question using only the data below. The data has three parts:
- Facts computed by the app from coordinates and station records. They are exact. Cite them as Facts (F1).
- Relationships from the campus knowledge graph. Cite them as Relationships (id).
- Source texts. Cite them as Sources (id).
Put the citations at the end of the sentence they support, for example [Data: Facts (F2); Sources (14)].

{task}

Rules:
- Never state live bike or dock counts; the app shows them next to your answer.
- Distances are straight-line estimates, so say "about".
- If the data does not answer part of the question, say so instead of guessing.
- Answer in the language of the question.

---Data---

{data}"""

TASK_STATION = """The question is about which YouBike station to use. Answer in this shape, in plain sentences:
**Station:** the station you recommend and its distance from the place in the question.
**Why:** two to four short reasons taken from the data, such as the gate to leave by, where the station is marked and how to recognise it, and what the snapshots show for that station at the time asked.
**Backup:** the next best station and when to use it.
If the Facts say a station was often short at the time asked, prefer a nearby station that was not, and say why.
The bike patterns come from a small sample of snapshots: say "in our snapshots", not "always" or "usually". If the Facts say the hour was not sampled or had too few snapshots, say that this is not known.
If a Source and the Facts disagree about when a station is short, follow the Facts: they use the newer snapshots."""

TASK_GENERAL = """Answer the question directly in one or two short paragraphs. Use the relationships to connect the places involved (for example a department to its building, a building to a gate or a road)."""


def build_data(facts, ctx):
    lines = ["Facts:"] + [f"F{i}: {f}" for i, f in enumerate(facts, 1)]
    lines += ["", "Relationships (source -> target: description):"]
    lines += [f"[{r['id']}] {r['source']} -> {r['target']}: {r['description']}" for r in ctx["relationships"]] or ["(none)"]
    lines += ["", "Sources:"]
    lines += [f"[{c['id']}] (file {c['doc']})\n{c['text'].strip()}\n" for c in ctx["sources"]] or ["(none)"]
    return "\n".join(lines)


def _model(root, overrides):
    """Model name, Ollama address and options from settings.yaml (plus overrides)."""
    from graphrag.config.load_config import load_config

    cwd = os.getcwd()
    try:  # load_config changes the working directory; put it back
        cfg = load_config(root_dir=Path(root), cli_overrides=_merge({}, overrides or {}))
    finally:
        os.chdir(cwd)
    m = cfg.completion_models["default_completion_model"]
    return m.model, (m.api_base or "http://localhost:11434").rstrip("/"), dict(m.call_args or {})


def chat(system, question, root, overrides=None):
    model, base, args = _model(root, overrides)
    body = {"model": model, "stream": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": question}],
            "options": {"temperature": 0, "seed": args.get("seed", 42), "num_ctx": args.get("num_ctx", 8192),
                        "num_predict": args.get("max_tokens", 1500)}}
    if args.get("think") is False and "instruct" not in model:
        body["think"] = False  # hybrid thinking models such as qwen3:8b
    r = requests.post(f"{base}/api/chat", json=body, timeout=args.get("timeout", 1200))
    r.raise_for_status()
    data = r.json()
    return data["message"]["content"], data.get("prompt_eval_count"), data.get("eval_count")


def answer(question, root=None, response_type=None, overrides=None, live=True, k=K_STATIONS):
    """Same result shape as hybrid.answer, with mode 'hybrid2'."""
    root = Path(root or GRAPHRAG_ROOT)
    start = time.perf_counter()
    places = [p for p in find_places(question, hybrid.buildings()) if p.get("lat") is not None]
    if not places:  # nothing to start a route from: same as Local search
        res = hybrid.answer(question, "local", root=root, overrides=overrides)
        res["mode"] = "hybrid2"
        res["notes"] = res.get("notes", []) + ["No campus place was recognised, so this is a plain Local search answer."]
        return res
    place = places[0]
    stations_wanted = bool(STATION_WORDS.search(question))
    returning = bool(RETURN_WORDS.search(question))
    hour = parse_hour(question)

    dist = {s["sno"]: round(hybrid.ns.haversine_m(place["lat"], place["lng"], float(s["lat"]), float(s["lng"])))
            for s in hybrid.campus_stations()}
    snos = sorted(dist, key=dist.get)[:k]
    feed, live_error = None, None
    try:
        feed = hybrid.ns.fetch_stations() if live else None
    except Exception as exc:  # network down, API changed, ...
        live_error = f"{type(exc).__name__}: {exc}"
    cards = hybrid.live_cards(snos, feed, dist)
    # a question that is not about stations gets only the nearest one as a side fact
    facts, campus_edges = campus_facts(root, places, cards if stations_wanted else cards[:1], hour, returning)

    kg = kg_for(root)
    ctx = {"relationships": [], "sources": [], "entities": []}
    if kg is not None:
        gates = [b for b in hybrid.buildings() if b.get("category") == "gate"]
        place_titles = [t for p in places for t in link_place(kg, p)]
        gate_titles = []
        pg = nearest_gate(place, [g for g in gates if g.get("lat") is not None])
        for gname in ([pg[0]["name"]] if pg else []) + [station_profile(str(root), c["sno"])["gate"][0]
                                                       for c in cards[:3] if station_profile(str(root), c["sno"])["gate"]]:
            g = next((x for x in gates if x["name"] == gname), None)
            if g:
                gate_titles += [t for t in link_place(kg, g) if t not in gate_titles]
        station_titles = [t for c in cards[:3] for t in link_station(kg, c)] if stations_wanted else []
        docs = [p["doc_group"] for p in places if p.get("doc_group")]
        docs += [f"station_{c['sno']}" for c in cards[:3]] if stations_wanted else []
        ctx = graph_context(kg, place_titles, gate_titles, station_titles, docs)

    system = SYSTEM.format(task=TASK_STATION if stations_wanted else TASK_GENERAL, data=build_data(facts, ctx))
    text, p_tok, c_tok = chat(system, question, root, overrides)

    sources = [("facts", f"F{i}", f) for i, f in enumerate(facts, 1)]
    sources += [("relationships", f"{r['source']} -> {r['target']}", r["description"]) for r in ctx["relationships"]]
    sources += [("sources", c["doc"], c["text"]) for c in ctx["sources"]]
    return {
        "question": question, "mode": "hybrid2", "place": place["name"],
        "place_coords": (place["lat"], place["lng"]), "stations": cards,
        "live_error": live_error, "notes": [], "answer": text, "sources": sources,
        "seconds": time.perf_counter() - start,
        "graph_context": {"entities": ctx["entities"], "relationships": [(r["source"], r["target"]) for r in ctx["relationships"]],
                          "reports": [], "sources": len(ctx["sources"])},
        "context": {"sources": ctx["sources"], "relationships": ctx["relationships"],
                    "entities": [{"entity": e} for e in ctx["entities"]], "facts": facts},
        "route": {"places": [p["name"] for p in places], "hour": hour, "returning": returning,
                  "campus_edges": campus_edges},
        "prompt_tokens": p_tok, "completion_tokens": c_tok,
    }
