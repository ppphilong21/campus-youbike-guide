"""Campus YouBike Guide: demo app.

Run from the repo folder:  streamlit run app/streamlit_app.py
"""
import csv
import datetime as dt
import sys
from pathlib import Path

import streamlit as st

APP = Path(__file__).resolve().parent
ROOT = APP.parent
sys.path.insert(0, str(APP))
import hybrid  # noqa: E402

MODES = {
    "Hybrid (Local search + live YouBike data)": "hybrid",
    "Local search": "local",
    "Global search": "global",
    "DRIFT search": "drift",
    "Basic search (traditional RAG)": "basic",
}
EXAMPLES = [
    "Which station near the library should I use at 8 am, and how do I recognise it?",
    "I am an international student living in the dormitory. Which YouBike station should I use to get to the CSIE department?",
    "What should a new student know before using YouBike around campus?",
]


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


st.set_page_config(page_title="Campus YouBike Guide", page_icon="🚲", layout="wide")
st.title("Campus YouBike Guide")
st.caption("Taiwan Tech · GraphRAG on a local model, with live YouBike availability")

with st.sidebar:
    mode_label = st.radio("Retrieval mode", list(MODES), index=0)
    st.caption("Hybrid adds the nearest stations and live counts. The other modes are plain GraphRAG, "
               "for comparing retrieval strategies.")
    st.divider()
    st.caption("Example questions")
    for i, ex in enumerate(EXAMPLES):
        if st.button(ex, key=f"ex{i}", use_container_width=True):
            st.session_state["question"] = ex

question = st.text_input("Ask about getting around campus by YouBike", key="question",
                         placeholder="e.g. Which station is closest to the IB building?")
ask = st.button("Ask", type="primary", disabled=not question)

if ask and question:
    with st.spinner("Searching the knowledge graph. On a CPU laptop this can take a minute or two..."):
        try:
            res = hybrid.answer(question, MODES[mode_label])
            st.session_state["result"] = res
            log_query(res)
        except Exception as exc:
            st.session_state["result"] = None
            st.error(f"The query failed: {type(exc).__name__}: {exc}")
            st.info("Check that Ollama is running and that `graphrag index` has finished. "
                    "See 'Khi bị kẹt' in the weekly guide.")

res = st.session_state.get("result")
if res:
    st.subheader("Answer")
    st.markdown(res["answer"])
    meta = [mode_label if MODES[mode_label] == res["mode"] else res["mode"], f"{res['seconds']:.0f} s"]
    if res["place"]:
        meta.append(f"place recognised: {res['place']}")
    st.caption(" · ".join(meta))
    for note in res.get("notes", []):
        st.warning(note)

    if res["mode"] == "hybrid":
        if res["live_error"]:
            st.warning("Live bike counts could not be verified right now, so no numbers are shown. "
                       "Check the official YouBike app before you go.")
        if res["stations"]:
            st.subheader("Nearest stations")
            cols = st.columns(len(res["stations"]))
            for col, card in zip(cols, res["stations"]):
                with col, st.container(border=True):
                    st.markdown(f"**{card['name']}**")
                    sub = [card["name_zh"], f"station {card['sno']}"]
                    if card["distance_m"] is not None:
                        sub.insert(0, f"about {card['distance_m']} m")
                    st.caption(" · ".join(s for s in sub if s))
                    if card["bikes"] is not None:
                        a, b = st.columns(2)
                        a.metric("Bikes", card["bikes"])
                        b.metric("Free docks", card["free_docks"])
                        st.caption(f"Updated {card['updated']}" + ("" if card["active"] else " · station not active"))
                    if card["tour_url"]:
                        st.link_button("Open virtual tour", card["tour_url"], use_container_width=True)

    with st.expander(f"Sources used ({len(res['sources'])})"):
        for kind, title, text in res["sources"]:
            st.markdown(f"**{kind}** · {title}")
            st.text(text[:600] + ("..." if len(text) > 600 else ""))
