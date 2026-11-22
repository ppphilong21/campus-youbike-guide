"""Knowledge graph views for the app.

- full_graph(): the whole graph GraphRAG built, filtered by entity type or around one entity
- answer_subgraph(): only the entities and relationships one answer used, plus, in Hybrid
  mode, the distances the app computed from coordinates
- graph_html(): draws nodes and edges as an interactive vis-network page (pyvis), with the
  JavaScript inlined so it also works without internet during a demo

The graph is read from <root>/output/entities.parquet and relationships.parquet.
"""
import html
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

TYPE_COLORS = {
    "YOUBIKE_STATION": "#f08c00",
    "BUILDING": "#1c7ed6",
    "GATE": "#7048e8",
    "ROAD": "#868e96",
    "PARKING": "#495057",
    "BUS_STOP": "#0ca678",
    "LANDMARK": "#2f9e44",
    "FACILITY": "#1098ad",
    "DEPARTMENT": "#4263eb",
    "OFFICE": "#5f3dc4",
    "DISTRICT": "#74b816",
    "SERVICE": "#e8590c",
    "FEE": "#e03131",
    "RULE": "#c2255c",
    "PAYMENT_METHOD": "#ae3ec9",
    "USER_GROUP": "#d6336c",
}
OTHER_COLOR = "#adb5bd"
LIVE_COLOR = "#f08c00"
COMMUNITY_COLORS = ["#1c7ed6", "#f08c00", "#2f9e44", "#e03131", "#7048e8", "#0ca678", "#c2255c", "#5c940d",
                    "#1098ad", "#e8590c", "#4263eb", "#ae3ec9", "#868e96", "#d6336c", "#495057", "#74b816"]


def type_color(t):
    return TYPE_COLORS.get(str(t or "").upper(), OTHER_COLOR)


def _clean(text):
    """Entity text comes from the model, so angle brackets are replaced before it goes into the
    page: nothing it writes can close the script tag or add HTML."""
    return str(text or "").replace("<", "\u2039").replace(">", "\u203a")


KEEP_UPPER = {"NTU", "NTUST", "NTNU", "MRT", "TPASS", "IC", "QR", "NT", "CSIE", "ATM", "EV", "TV"}
SMALL_WORDS = {"AND", "OF", "THE", "TO", "FOR", "IN", "ON", "AT", "BY", "VIA", "A", "AN"}


def pretty(title):
    """GraphRAG stores names in capitals; show 'NTU AND NTNU' as 'NTU and NTNU', 'EE BUILDING' as
    'EE Building' and 'YOUBIKE 2.0E' as 'YouBike 2.0E'."""
    title = str(title or "")
    if not title.isupper():
        return title

    def word(m):
        w = m.group(0)
        if w == "YOUBIKE":
            return "YouBike"
        if w in SMALL_WORDS:
            return w.lower()
        if w in KEEP_UPPER or len(w) <= 2:
            return w
        return w.capitalize()

    out = re.sub(r"[A-Z]+", word, title)
    return out[0].upper() + out[1:] if out else out


def _short(text, n=300):
    text = " ".join(_clean(text).split())
    return text if len(text) <= n else text[: n - 3] + "..."


def load_graph(root):
    """Read the index once. Returns a dict, or None when the index is not there yet."""
    out = Path(root) / "output"
    if not (out / "entities.parquet").exists():
        return None
    ents = pd.read_parquet(out / "entities.parquet")
    rels = pd.read_parquet(out / "relationships.parquet")
    ents["type"] = ents["type"].fillna("").astype(str).str.upper()
    ents["description"] = ents["description"].fillna("")

    # Source files of each entity: entity -> text units -> documents
    files = defaultdict(set)
    if (out / "text_units.parquet").exists() and (out / "documents.parquet").exists():
        units = pd.read_parquet(out / "text_units.parquet")
        docs = pd.read_parquet(out / "documents.parquet")
        doc_title = dict(zip(docs["id"], docs["title"]))
        unit_doc = dict(zip(units["id"], units["document_id"]))
        for title, unit_ids in zip(ents["title"], ents["text_unit_ids"]):
            for u in list(unit_ids) if unit_ids is not None else []:
                if unit_doc.get(u) in doc_title:
                    files[title].add(doc_title[unit_doc[u]])

    # Community of each entity at the lowest level, for the "colour by community" option
    community = {}
    if (out / "communities.parquet").exists():
        comms = pd.read_parquet(out / "communities.parquet")
        id_to_title = dict(zip(ents["id"], ents["title"]))
        for _, c in comms.sort_values("level", ascending=False).iterrows():
            for eid in c["entity_ids"] if c["entity_ids"] is not None else []:
                if eid in id_to_title:
                    community[id_to_title[eid]] = int(c["community"])

    return {"root": str(root), "entities": ents, "relationships": rels,
            "files": {k: sorted(v) for k, v in files.items()}, "community": community,
            "by_title": {t: r for t, r in zip(ents["title"], ents.to_dict("records"))},
            "upper": {str(t).upper(): t for t in ents["title"]}}


def find_title(g, name):
    """Entity title in the graph for a name, ignoring case ('Library' -> 'LIBRARY')."""
    return g["upper"].get(str(name or "").strip().upper()) if g else None


def _node(g, title, color_by="type", highlight=False):
    row = g["by_title"].get(title, {})
    t = row.get("type", "")
    if color_by == "community":
        c = g["community"].get(title)
        color = COMMUNITY_COLORS[c % len(COMMUNITY_COLORS)] if c is not None else OTHER_COLOR
    else:
        color = type_color(t)
    degree = int(row.get("degree") or 0)
    files = ", ".join(g["files"].get(title, [])) or "-"
    label = _clean(pretty(title))
    return {"id": title, "label": label, "color": color,
            "size": 10 + min(degree, 20) * 1.5, "type": t or "ENTITY",
            "tooltip": f"{_clean(title)}\nType: {_clean(t) or '-'}   Links: {degree}\nFiles: {_clean(files)}\n\n{_short(row.get('description'))}",
            "border": highlight}


def full_graph(g, types=None, min_degree=0, focus=None, hops=1, color_by="type"):
    """Nodes and edges of the whole graph, or of the neighbourhood around `focus`."""
    ents, rels = g["entities"], g["relationships"]
    keep = set(ents["title"])
    if types:
        keep = set(ents.loc[ents["type"].isin(types), "title"])
    if min_degree:
        keep &= set(ents.loc[ents["degree"] >= min_degree, "title"])
    if focus:
        around = {focus}
        for _ in range(hops):
            nxt = set(rels.loc[rels["source"].isin(around), "target"]) | set(rels.loc[rels["target"].isin(around), "source"])
            around |= nxt
        keep = (keep & around) | {focus}
    nodes = [_node(g, t, color_by, highlight=(t == focus)) for t in sorted(keep)]
    edges = [{"from": r["source"], "to": r["target"], "tooltip": _short(r["description"], 200),
              "width": 1 + min(float(r.get("weight") or 1), 10) / 4}
             for r in rels.to_dict("records") if r["source"] in keep and r["target"] in keep]
    return nodes, edges


def answer_subgraph(g, entity_titles, rel_pairs, place=None, stations=()):
    """The part of the graph one answer used.

    entity_titles, rel_pairs: what the search put in the model's context.
    place, stations: Hybrid mode only. place is a name, stations are (name, distance_m).
    Edges: thick = given to the model, thin dashed = other links in the graph between the
    same entities, orange dashed = straight-line distance computed by the app.
    """
    titles = [t for t in entity_titles if t in g["by_title"]]
    nodes = {t: _node(g, t) for t in titles}
    edges, seen = [], set()
    rels = g["relationships"]
    for s, t in rel_pairs:
        if s in nodes and t in nodes:
            seen.add(frozenset((s, t)))
            desc = rels.loc[((rels["source"] == s) & (rels["target"] == t)) | ((rels["source"] == t) & (rels["target"] == s)), "description"]
            edges.append({"from": s, "to": t, "width": 3, "tooltip": _short(desc.iloc[0] if len(desc) else "", 200)})
    for r in rels.to_dict("records"):
        pair = frozenset((r["source"], r["target"]))
        if r["source"] in nodes and r["target"] in nodes and pair not in seen:
            seen.add(pair)
            edges.append({"from": r["source"], "to": r["target"], "width": 1, "dashes": True,
                          "tooltip": "In the graph, not given to the model: " + _short(r["description"], 160)})
    if place:
        p = find_title(g, place) or place
        if p not in nodes:
            nodes[p] = {"id": p, "label": _clean(place), "color": type_color("BUILDING"), "size": 18, "type": "PLACE",
                        "tooltip": f"{_clean(place)}\nRecognised in the question", "border": True}
        else:
            nodes[p]["border"] = True
        for name, dist in stations:
            sid = find_title(g, name) or find_title(g, f"{name} station") or f"{name} station"
            if sid not in nodes:
                nodes[sid] = {"id": sid, "label": _clean(f"{name} station"), "color": LIVE_COLOR, "size": 16,
                              "type": "YOUBIKE_STATION", "tooltip": _clean(f"{name} station\nFrom the live YouBike data"),
                              "border": False}
            edges.append({"from": p, "to": sid, "width": 2, "dashes": True, "color": LIVE_COLOR,
                          "label": f"{dist} m" if dist is not None else "",
                          "tooltip": "Straight-line distance computed by the app from coordinates"})
    return list(nodes.values()), edges


def graph_html(nodes, edges, height=620, physics=True):
    """Interactive graph as one HTML page (vis-network inlined, works offline)."""
    from pyvis.network import Network

    net = Network(height=f"{height}px", width="100%", bgcolor="#ffffff", font_color="#212529",
                  cdn_resources="in_line")
    for n in nodes:
        net.add_node(_clean(n["id"]), label=n["label"], title=n["tooltip"], color=n["color"], size=n["size"],
                     borderWidth=4 if n.get("border") else 1, shape="dot")
    for e in edges:
        kw = {k: e[k] for k in ("width", "dashes", "color", "label") if k in e and e[k] not in (None, "")}
        net.add_edge(_clean(e["from"]), _clean(e["to"]), title=e.get("tooltip", ""), **kw)
    net.set_options("""
    {
      "nodes": {"font": {"size": 13, "face": "Arial"}},
      "edges": {"color": {"color": "#adb5bd", "highlight": "#495057"}, "smooth": false, "font": {"size": 11, "align": "top"}},
      "interaction": {"hover": true, "tooltipDelay": 120, "navigationButtons": true, "keyboard": false},
      "physics": {"enabled": %s, "solver": "forceAtlas2Based",
                  "forceAtlas2Based": {"gravitationalConstant": -60, "springLength": 110, "avoidOverlap": 0.4},
                  "stabilization": {"iterations": 250}}
    }""" % ("true" if physics else "false"))
    page = net.generate_html()
    # Fit the whole graph in view once the layout settles, and again whenever the frame is
    # shown or resized (a graph drawn inside a hidden tab starts with zero size).
    fit = """
<script>
(function () {
  function fit() { try { network.fit({animation: false}); } catch (e) {} }
  try { network.once("stabilizationIterationsDone", fit); } catch (e) {}
  window.addEventListener("resize", fit);
  var el = document.getElementById("mynetwork");
  if (el && "IntersectionObserver" in window) {
    new IntersectionObserver(function (es) { if (es[0].isIntersecting) { fit(); } }).observe(el);
  }
  setTimeout(fit, 1500);
})();
</script>
"""
    return page.replace("</body>", fit + "</body>") if "</body>" in page else page + fit


def legend_html(types):
    chips = "".join(
        f'<span style="display:inline-block;margin:2px 10px 2px 0;font-size:13px">'
        f'<span style="display:inline-block;width:11px;height:11px;border-radius:50%;background:{type_color(t)};'
        f'margin-right:5px;vertical-align:-1px"></span>{html.escape(t.replace("_", " ").lower())}</span>' for t in types)
    return f"<div>{chips}</div>"


def entity_details(g, title):
    """Description, files and neighbours of one entity, for the details panel."""
    row = g["by_title"].get(title)
    if row is None:
        return None
    rels = g["relationships"]
    links = [(r["target"] if r["source"] == title else r["source"], r["description"])
             for r in rels.to_dict("records") if title in (r["source"], r["target"])]
    return {"title": title, "type": row.get("type", ""), "degree": int(row.get("degree") or 0),
            "description": row.get("description", ""), "files": g["files"].get(title, []), "links": links}
