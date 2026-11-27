"""Campus YouBike Guide: demo app.

Run from the repo folder:  python -m streamlit run app/streamlit_app.py

Views (switch at the top right):
- Ask: question box with the retrieval-mode menu and the user's location (the browser asks for it
  when the page opens), the place asked about
  (photo, nearest 360° view), the walking route on the photographed
  campus paths, nearest station with live counts and a map, the answer with its citations, the
  part of the knowledge graph it used, and its sources
- Knowledge graph: the whole graph GraphRAG built, with filters and entity details

Styles and card HTML live in ui.py; answering in hybrid.py; graph drawing in kg_view.py.
"""
import csv
import datetime as dt
import re
import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

APP = Path(__file__).resolve().parent
ROOT = APP.parent
sys.path.insert(0, str(APP))
import demo_cache  # noqa: E402
import hybrid  # noqa: E402
import kg_view  # noqa: E402
import ui  # noqa: E402
import walk_route  # noqa: E402
from graph_query import GRAPHRAG_ROOT  # noqa: E402

# The browser position: an invisible component in app/components/geolocation (no extra package)
_geolocation = components.declare_component("geolocation", path=str(APP / "components" / "geolocation"))
ROUGH_M = 60  # a position reported with a wider error than this is shown as "around" a place

EXAMPLES = [
    "Which station near the library should I use at 8 am, and how do I recognise it?",
    "I live in the dormitory. Which station should I use to get to the CSIE department?",
    "What should a new student know before using YouBike around campus?",
]
CAMPUS = {"administration", "academic", "public", "dining", "dormitory", "sports"}
VIEWS = {"Ask": ":material/chat_bubble: Ask", "Knowledge graph": ":material/account_tree: Knowledge graph"}


def log_query(res):
    """Append timing to notes/query_log.csv (used for the Local AI Deployment section)."""
    path = ROOT / "notes" / "query_log.csv"
    path.parent.mkdir(exist_ok=True)
    new = not path.exists()
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "mode", "seconds", "place", "question"])
        w.writerow([dt.datetime.now().isoformat(timespec="seconds"), res["mode"], f"{res['seconds']:.1f}",
                    res["place"] or "", res["question"]])


def index_folders():
    """GraphRAG folders that have a finished index, the configured one first."""
    found = []
    for p in (GRAPHRAG_ROOT, ROOT / "graphrag", ROOT / "graphrag_test"):
        p = Path(p).resolve()
        if p not in found and (p / "output" / "entities.parquet").exists():
            found.append(p)
    return found or [Path(GRAPHRAG_ROOT).resolve()]


def render_html(page, height):
    """Interactive graph page in an iframe (st.iframe in new Streamlit, components.html before)."""
    if hasattr(st, "iframe"):
        st.iframe(page, height=height)
    else:
        components.html(page, height=height)


@st.cache_resource(show_spinner="Loading the knowledge graph...")
def graph_for(root, mtime):  # mtime makes the cache reload after a new index run
    return kg_view.load_graph(root)


def load_graph(root):
    f = Path(root) / "output" / "entities.parquet"
    return graph_for(str(root), f.stat().st_mtime if f.exists() else 0)


def community_count(root, g):
    """'37' communities with reports in all levels; the graph colours use one level (16 groups)."""
    try:
        import pandas as pd
        c = pd.read_parquet(Path(root) / "output" / "communities.parquet", columns=["level"])
        return len(c), int((c["level"] == c["level"].min()).sum())
    except Exception:
        n = len(set(g["community"].values())) if g else 0
        return n, n


def index_stats(root, g):
    docs = 0
    try:
        import pandas as pd
        docs = len(pd.read_parquet(Path(root) / "output" / "documents.parquet", columns=["id"]))
    except Exception:
        pass
    if g is None:
        return [("documents", docs)]
    return [("documents", docs), ("entities", len(g["entities"])), ("relationships", len(g["relationships"])),
            (f"communities, {community_count(root, g)[1]} top-level", community_count(root, g)[0])]


def show_map(res, height=360):
    """Recognised place, nearest stations with live counts, and the rest of campus faintly."""
    import pydeck as pdk

    points, lines, labels = [], [], []
    for b in hybrid.buildings():
        if b["lat"] is not None and b.get("category") in CAMPUS:
            points.append({"name": b["name"], "info": "Campus building", "lat": b["lat"], "lng": b["lng"],
                           "color": [134, 150, 170, 110], "radius": 5})
    near = {c["sno"] for c in res["stations"]}
    for s in hybrid.campus_stations():
        if s["sno"] not in near:
            points.append({"name": hybrid._short(s["snaen"] or s["sna"]) + " station", "info": "Other YouBike station",
                           "lat": float(s["lat"]), "lng": float(s["lng"]), "color": [255, 157, 25, 110], "radius": 7})
    place = res.get("place_coords")
    walk = res.get("walk")
    nodes = walk_route.graph()[0]
    paths, route_pts = [], []
    if walk:
        pts = [walk["origin_pt"]] + [(nodes[n]["lat"], nodes[n]["lng"]) for n in walk.get("nodes", []) if n in nodes]
        pts.append(walk["dest_pt"])
        paths.append({"name": f"Walk {walk['origin']} to {walk['dest']}", "info": f"about {walk['metres']} m",
                      "path": [[lng, lat] for lat, lng in pts]})
        for n in walk.get("nodes", []):
            if n in nodes:
                route_pts.append({"name": nodes[n]["name"], "info": f"360° view {n}: {nodes[n]['where']}",
                                  "lat": nodes[n]["lat"], "lng": nodes[n]["lng"], "color": [0, 91, 172, 255], "radius": 6})
        for (lat, lng), name, color in ((walk["origin_pt"], walk["origin"], [0, 91, 172, 240]),
                                        (walk["dest_pt"], walk["dest"], [255, 157, 25, 250])):
            route_pts.append({"name": name, "info": "start" if color[0] == 0 else "destination", "lat": lat, "lng": lng,
                              "color": color, "radius": 13})
            labels.append({"name": name, "info": "", "lat": lat, "lng": lng})
    here = res.get("here")
    if here:
        acc = here.get("accuracy") or 0
        if acc:
            points.append({"name": "Your location", "info": f"accurate to about {round(acc)} m", "lat": here["lat"],
                           "lng": here["lng"], "color": [0, 91, 172, 40], "radius": min(acc, 200)})
        route_pts.append({"name": "You are here", "info": here.get("near") and f"near {here['near']}" or "",
                          "lat": here["lat"], "lng": here["lng"], "color": [0, 91, 172, 255], "radius": 9})
    for c in res["stations"]:
        if not c.get("lat"):
            continue
        if c["bikes"] is None:
            color, info = [156, 163, 175, 230], "no live data"
        else:
            color = [220, 38, 38, 230] if c["bikes"] == 0 else [245, 158, 11, 230] if c["bikes"] < 3 else [22, 163, 74, 230]
            info = f"{c['bikes']} bikes, {c['free_docks']} free docks"
        if c["distance_m"] is not None:
            info = f"about {c['distance_m']} m. {info}"
        points.append({"name": c["name"] + " station", "info": info, "lat": c["lat"], "lng": c["lng"],
                       "color": color, "radius": 13})
        labels.append({"name": c["name"], "info": info, "lat": c["lat"], "lng": c["lng"]})
        if place and not walk:
            lines.append({"name": c["name"], "info": info, "from": [place[1], place[0]], "to": [c["lng"], c["lat"]]})
    if place and not walk and not (here and res.get("place") == "your location"):
        points.append({"name": res["place"], "info": "Place recognised in the question", "lat": place[0],
                       "lng": place[1], "color": [0, 91, 172, 240], "radius": 14})
        labels.append({"name": res["place"], "info": "", "lat": place[0], "lng": place[1]})
    focus = ([p for p in route_pts if p["radius"] >= 9] if walk else []) or [p for p in points if p["radius"] >= 13] or points
    view = pdk.ViewState(latitude=sum(p["lat"] for p in focus) / len(focus),
                         longitude=sum(p["lng"] for p in focus) / len(focus), zoom=16.3)
    layers = [
        pdk.Layer("LineLayer", lines, get_source_position="from", get_target_position="to",
                  get_color=[255, 157, 25, 170], get_width=2),
        pdk.Layer("PathLayer", paths, get_path="path", get_color=[0, 91, 172, 220], get_width=4,
                  width_min_pixels=4, pickable=True),  # width in metres, at least 4 px on screen
        pdk.Layer("ScatterplotLayer", points + route_pts, get_position="[lng, lat]", get_fill_color="color",
                  get_radius="radius", pickable=True),  # radius in metres; extra radius/line options broke sizing
        pdk.Layer("TextLayer", labels, get_position="[lng, lat]", get_text="name", get_size=13,
                  get_color=[14, 42, 71], get_pixel_offset=[0, -18], font_weight=700,
                  outline_width=3, outline_color=[255, 255, 255], font_settings={"sdf": True}),
    ]
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view, map_provider="carto", map_style="light",
                             tooltip={"html": "<b>{name}</b><br/>{info}"}), height=height)
    st.markdown(ui.map_legend(), unsafe_allow_html=True)


def show_how(res, g):
    """The part of the knowledge graph this answer used."""
    gc = res.get("graph_context") or {}
    if res["mode"] == "basic":
        st.info(f"Basic search (traditional RAG) does not use the knowledge graph. It found "
                f"{gc.get('sources', 0)} text chunks by similarity; they are listed under Sources.")
        return
    if gc.get("reports") and not gc.get("entities"):
        st.info("This answer was written from community summaries (the clusters of the graph):\n\n"
                + "\n".join(f"- {t}" for t in gc["reports"][:10]))
        return
    if g is None or not gc.get("entities"):
        st.caption("This answer's context has no graph entities to draw.")
        return
    hybrid_mode = res["mode"] in ("hybrid", "hybrid2") and res.get("place")
    nodes, edges = kg_view.answer_subgraph(
        g, gc["entities"], gc["relationships"],
        place=res["place"] if hybrid_mode else None,
        stations=[(c["name"], c["distance_m"]) for c in res["stations"]] if hybrid_mode else ())
    render_html(kg_view.graph_html(nodes, edges, height=470), height=490)
    st.markdown(kg_view.legend_html(sorted({n["type"] for n in nodes if n["type"] in kg_view.TYPE_COLORS})),
                unsafe_allow_html=True)
    n_e, n_r = len(gc["entities"]), len(gc["relationships"])
    st.caption(f"{n_e} {'entity' if n_e == 1 else 'entities'} and {n_r} {'relationship' if n_r == 1 else 'relationships'} "
               "were given to the model. "
               "Thick lines: relationships in the model's context. Thin dashed lines: other links in the graph "
               "between the same entities." + (" Orange dashed lines: distances the app computed from coordinates "
                                                "and live data, not from the graph." if hybrid_mode else ""))


def ask_example(question):
    st.session_state["question"] = question
    st.session_state["pending"] = True
    st.session_state["view"] = "Ask"


def set_mode():
    st.session_state["mode"] = st.session_state["mode_choice"]


def mode_menu():
    """The retrieval-mode picker, shaped like the model menu of a chat app.

    The choice is kept in session_state["mode"], so it survives a visit to the graph view.
    """
    keys = [m[0] for m in ui.MODES]
    _, name, _, _, icon = ui.MODE[st.session_state["mode"]]
    with st.popover(f"{icon} {name}"):
        st.markdown('<div class="yb-menu-title">Retrieval mode</div>', unsafe_allow_html=True)
        st.radio("Retrieval mode", keys, index=keys.index(st.session_state["mode"]), key="mode_choice",
                 on_change=set_mode, label_visibility="collapsed",
                 format_func=lambda k: f"{ui.MODE[k][4]} **{ui.MODE[k][1]}**",
                 captions=[f"{m[2]} · {ui.minutes(m[3])}" for m in ui.MODES])


def show_answer(res, graph):
    st.markdown(f'<div class="yb-note" style="margin-top:18px">You asked · <b style="color:#0E2A47">'
                f'{ui.esc(res["question"])}</b></div>', unsafe_allow_html=True)
    for note in res.get("notes", []):
        st.warning(note)
    if res.get("place_card") or res.get("walk"):
        show_place(res)
    if res["mode"] in ("hybrid", "hybrid2"):
        if res["stations"]:
            meta = {s["sno"]: s for s in hybrid.campus_stations()}
            with st.container(key="hero"):
                st.markdown(ui.hero_head(res), unsafe_allow_html=True)
                left, right = st.columns([1.1, 1], gap="medium")
                left.markdown(ui.hero_left(res, meta), unsafe_allow_html=True)
                if any(c.get("lat") for c in res["stations"]):
                    with right:
                        show_map(res)
            st.markdown(ui.other_stations(res["stations"][1:]), unsafe_allow_html=True)
        elif not res.get("place"):
            st.caption("No campus place was recognised in the question, so no stations are shown.")

    text, cites = ui.split_citations(res["answer"])
    with st.container(key="answer"):
        st.markdown(ui.answer_chips(res), unsafe_allow_html=True)
        st.markdown(f'<div class="yb-answer-title">{ui.esc(ui.answer_title(res, text))}</div>', unsafe_allow_html=True)
        st.markdown(text.replace("$", r"\$"))  # NT$ amounts are not LaTeX
        if cites:
            st.markdown(f'<div class="yb-cite">{ui.esc(cites)}</div>', unsafe_allow_html=True)

    st.write("")
    with st.expander("How this answer was found", icon=":material/account_tree:"):
        show_how(res, graph)
    with st.expander(f"Sources used ({len(res['sources'])})", icon=":material/description:"):
        st.markdown(ui.sources_html(res["sources"]), unsafe_allow_html=True)


def show_place(res):
    """The place asked about (photo, nearest 360° view) and the walking route."""
    card, walk = res.get("place_card"), res.get("walk")
    with st.container(key="placecard"):
        photo = (card or {}).get("photo")
        if photo and Path(photo["file"]).exists():
            c1, c2 = st.columns([1, 3], gap="medium")
            c1.image(photo["file"], caption=photo.get("credit") or None)
            box = c2
        else:
            box = st.container()
        if card:
            kicker = ("Nearest place to your location" if res.get("place") == "your location" and not walk
                      else "Where you are going" if walk else "Place in your question")
            box.markdown(ui.place_card_html(card, kicker), unsafe_allow_html=True)
        if walk:
            box.markdown(ui.route_html(walk, walk_route.graph()[0]), unsafe_allow_html=True)


def browser_location():
    """The device position from the browser (GPS on a phone, Wi-Fi on a laptop).

    The component is invisible. On the first visit it asks by itself, so the browser shows its
    "allow location" prompt when the page opens; after that it asks each time geo_req grows
    (the "Use my device location" button). Called before the location menu is drawn, so a new
    position can clear the building picked in that menu.
    """
    auto = not st.session_state.get("geo_asked") and not st.session_state.get("here")
    with st.container(key="geobox"):
        val = _geolocation(auto=auto, req=st.session_state.get("geo_req", 0), key="geo", default=None)
    if val and val.get("ts") != st.session_state.get("geo_ts"):
        st.session_state["geo_ts"] = val["ts"]
        st.session_state["geo_asked"] = True
        st.session_state["geo_pending"] = False
        if val.get("error"):
            st.session_state["geo_error"] = val["error"]
        elif val.get("lat") is not None:
            st.session_state["geo_error"] = None
            st.session_state.pop("fix_place", None)
            st.session_state["here"] = {"lat": val["lat"], "lng": val["lng"], "accuracy": val.get("accuracy"),
                                        "near": graph_route_near(val), "source": "device"}
        st.rerun()


def location_label(here):
    if st.session_state.get("geo_pending"):
        return ":material/my_location: Finding you…"
    if not here:
        err = st.session_state.get("geo_error")
        if err == "blocked":
            return ":material/location_off: Location blocked"
        if err:
            return ":material/location_off: Location not available"
        return ":material/location_on: Use my location"
    near, acc = here.get("near"), here.get("accuracy")
    if here.get("source") == "picked":
        return f":material/location_on: At {near}"
    err = f" · ±{round(acc)} m" if acc else ""
    if not near:
        return f":material/my_location: Location on{err}"
    # a laptop locates by Wi-Fi: say "around" when the browser itself reports a wide error
    return f":material/my_location: {'Around' if acc and acc > ROUGH_M else 'Near'} {near}{err}"


def location_menu():
    """One control for the user's location, next to the mode menu.

    The button shows where the app thinks the user is. Its menu lets the user type the building
    they are in (when the browser position is off: a laptop locates by Wi-Fi, often 100 m or more),
    ask the device again, or stop using the location.
    """
    here = st.session_state.get("here")
    with st.container(key="loc_on" if here else "loc_off"):
        with st.popover(location_label(here)):
            with st.container(key="locmenu"):
                st.markdown('<div class="yb-menu-title">Your location</div>', unsafe_allow_html=True)
                st.caption(location_note(here))
                places = sorted(b["name"] for b in hybrid.buildings()
                                if b.get("lat") is not None and b.get("category") not in ("neighbour", "security"))
                ask = "Not right? Type where you are" if here and here.get("source") == "device" else "Type where you are"
                st.selectbox(ask, places, index=None,
                             placeholder="Type a building, e.g. Library", key="fix_place", on_change=set_fixed_place)
                st.button("Use my device location", icon=":material/my_location:", key="geo_again",
                          on_click=request_location)
                if here:
                    st.button("Stop using my location", icon=":material/location_off:", key="geo_off",
                              on_click=clear_location)


def location_note(here):
    err = st.session_state.get("geo_error")
    if not here:
        if err == "blocked":
            return ("The browser blocks the location for this page. Allow it from the lock icon next to the "
                    "address, or type where you are below.")
        if err:
            return "The device could not find its position. Type where you are below."
        return "Questions like \"nearest station to me\" start from your location."
    if here.get("source") == "picked":
        return f"Set by hand: {here['near']}. Questions like \"nearest station to me\" start here."
    acc = here.get("accuracy")
    where = f"near {here['near']}" if here.get("near") else "outside the campus"
    text = f"The browser places you {where}" + (f", within about {round(acc)} m." if acc else ".")
    if acc and acc > ROUGH_M:
        text += " A laptop locates by Wi-Fi, so this can be a building or two off."
    return text


def set_fixed_place():
    b = next((x for x in hybrid.buildings() if x["name"] == st.session_state.get("fix_place")), None)
    if b and b.get("lat") is not None:
        st.session_state["here"] = {"lat": b["lat"], "lng": b["lng"], "accuracy": None, "near": b["name"],
                                    "source": "picked"}
        st.session_state["geo_pending"] = False


def request_location():
    st.session_state["geo_req"] = st.session_state.get("geo_req", 0) + 1
    st.session_state["geo_pending"] = True
    st.session_state["geo_error"] = None


def clear_location():
    st.session_state.pop("here", None)
    st.session_state["fix_place"] = None
    st.session_state["geo_asked"] = True
    st.session_state["geo_pending"] = False


def graph_route_near(point):
    import graph_route
    p = graph_route.nearest_place({"lat": point["lat"], "lng": point["lng"]}, max_m=400)
    return p["name"] if p else None


def recorded_mode():
    """Recorded answers (scripts/cache_demo.py) are used when the page is opened with ?recorded=1."""
    return str(st.query_params.get("recorded", "")).lower() in ("1", "true", "yes", "on")


def show_graph_view(graph, root):
    if graph is None:
        st.info(f"No finished index in `{Path(root).name}` yet. Run `graphrag index --root {Path(root).name}` first.")
        return
    ents = graph["entities"]
    counts = ents["type"].value_counts()
    n_comm, n_top = community_count(root, graph)
    st.markdown(f'<div class="yb-section"><div><h3>Knowledge graph</h3><p>Index <code>{ui.esc(Path(root).name)}</code>: '
                f'{len(ents)} entities, {len(graph["relationships"])} relationships, '
                f'{n_comm} communities ({n_top} top-level).</p></div></div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([4, 4, 2, 2])
    types = c1.multiselect("Entity types", list(counts.index), default=list(counts.index),
                           format_func=lambda t: f"{t.replace('_', ' ').lower()} ({counts[t]})")
    titles = sorted(ents["title"])
    focus = c2.selectbox("Focus on an entity", ["(whole graph)"] + titles)
    focus = None if focus == "(whole graph)" else focus
    hops = c3.slider("Steps from focus", 1, 3, 1, disabled=focus is None)
    color_by = c4.radio("Colour by", ["Entity type", "Community"])
    hide_isolated = st.checkbox("Hide entities with no relationships", value=True)

    nodes, edges = kg_view.full_graph(graph, types=types, min_degree=1 if hide_isolated else 0, focus=focus,
                                      hops=hops, color_by="community" if color_by == "Community" else "type")
    st.caption(f"Showing {len(nodes)} entities and {len(edges)} relationships. "
               "Drag to move, scroll to zoom, hover a node or a line for details.")
    if color_by == "Entity type":
        st.markdown(kg_view.legend_html([t for t in counts.index if t in types]), unsafe_allow_html=True)
    else:
        st.caption("Each colour is one community found by the Leiden algorithm; GraphRAG writes one summary report per community.")
    if nodes:
        render_html(kg_view.graph_html(nodes, edges, height=640), height=660)

    pick = st.selectbox("Entity details", titles, index=titles.index(focus) if focus in titles else 0)
    d = kg_view.entity_details(graph, pick)
    if d:
        raw = d.get("type_raw", "").replace("_", " ").lower()
        shown = d["type"].replace("_", " ").lower()
        st.markdown(f"**{d['title']}** · {shown or 'entity'} · {d['degree']} relationships"
                    + (f" · extracted as *{raw}*, outside the schema" if raw and raw != shown else ""))
        st.write(d["description"])
        if d["files"]:
            st.caption("Found in: " + ", ".join(d["files"]))
        for other, desc in d["links"][:30]:
            st.markdown(f"- **{other}**: {desc}")


# ---------------------------------------------------------------- page
st.set_page_config(page_title="Campus YouBike Guide", page_icon="🚲", layout="wide",
                   initial_sidebar_state="expanded")
st.markdown(ui.CSS, unsafe_allow_html=True)
st.session_state.setdefault("mode", "hybrid2")
if st.session_state["mode"] not in {m[0] for m in ui.MODES}:  # e.g. "hybrid" from an older session
    st.session_state["mode"] = "hybrid2"
st.session_state.setdefault("view", "Ask")

root = index_folders()[0]  # graphrag/ (or GRAPHRAG_ROOT); graphrag_test only if the full index is missing
with st.sidebar:
    st.markdown(ui.sidebar_brand(), unsafe_allow_html=True)
    st.markdown('<div class="yb-side-label">Try asking</div>', unsafe_allow_html=True)
    for i, ex in enumerate(EXAMPLES):
        st.button(ex, key=f"ex{i}", on_click=ask_example, args=(ex,))

graph = load_graph(root)

head, switch = st.columns([3, 1.3], vertical_alignment="bottom")
head.markdown(ui.page_header(), unsafe_allow_html=True)
with switch.container(key="viewbar"):
    st.radio("View", list(VIEWS), key="view", horizontal=True, label_visibility="collapsed",
             format_func=lambda v: VIEWS[v])

if st.session_state["view"] == "Knowledge graph":
    show_graph_view(graph, root)
else:
    with st.container(key="composer"):
        with st.form("ask_form", border=False, enter_to_submit=True):
            c1, c2 = st.columns([10, 1.5], vertical_alignment="center")
            c1.text_input("Question", key="question", label_visibility="collapsed",
                          placeholder="Ask about campus YouBike stations, e.g. Which station is closest to the IB building?")
            submitted = c2.form_submit_button("Ask", icon=":material/send:")
        browser_location()
        with st.container(key="modebar"):
            m1, m2, m3 = st.columns(3, vertical_alignment="center")
            with m1:
                mode_menu()
            with m2:
                location_menu()
            hint = "Recorded answers on · Enter to ask" if recorded_mode() else "Enter to ask"
            m3.markdown(f'<div class="yb-hint">{hint}</div>', unsafe_allow_html=True)

    # a question pasted from a list keeps its bullet ("• How do I get from IB to TR?"): drop it
    question = re.sub(r"^[\s•·▪●◦*\-–—]+", "", st.session_state.get("question") or "").strip()
    if (submitted or st.session_state.pop("pending", False)) and question:
        mode = st.session_state["mode"]
        here = st.session_state.get("here")
        cached = demo_cache.load(mode, question) if recorded_mode() else None
        with st.spinner(f"Searching with {ui.MODE[mode][1]} mode. This might take a few minutes..."):
            try:
                res = cached or hybrid.answer(question, mode, root=root, here=here)
                st.session_state["result"] = res
                if not cached:
                    log_query(res)
            except Exception as exc:
                st.session_state["result"] = None
                st.error(f"The query failed: {type(exc).__name__}: {exc}")
                st.info("Check that Ollama is running and that `graphrag index` has finished.")

    res = st.session_state.get("result")
    if res:
        show_answer(res, graph)
    else:
        st.markdown(ui.empty_state(index_stats(root, graph)), unsafe_allow_html=True)
