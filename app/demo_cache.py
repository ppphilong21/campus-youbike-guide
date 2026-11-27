"""Recorded answers for the live demo.

An answer takes 1.5 to 4 minutes on the CPU laptop, which is too long to wait in front of an
audience. scripts/cache_demo.py records answers to the demo questions beforehand; when the
app is opened with ?recorded=1, a question that was recorded (same mode, same
words) is shown at once, clearly labelled as recorded. The station cards are refreshed with
live counts from the YouBike API, so only the text was recorded.
"""
import datetime as dt
import hashlib
import json
import re

import hybrid

CACHE = hybrid.ROOT / "data" / "demo_cache"


def _key(mode, question):
    norm = re.sub(r"\s+", " ", question.strip().lower()).rstrip("?.!。？ ")
    return hashlib.sha1(f"{mode}|{norm}".encode("utf-8")).hexdigest()[:16]


def _plain(obj):
    """JSON-safe copy: tuples become lists, anything unknown (DataFrames) is dropped."""
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items() if _ok(v)}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj if _ok(v)]
    return obj


def _ok(v):
    return v is None or isinstance(v, (str, int, float, bool, dict, list, tuple))


def save(res):
    CACHE.mkdir(parents=True, exist_ok=True)
    keep = {k: v for k, v in res.items() if k != "context" or res.get("mode") == "hybrid2"}
    keep["recorded"] = dt.datetime.now().isoformat(timespec="minutes")
    path = CACHE / f"{_key(res['mode'], res['question'])}.json"
    path.write_text(json.dumps(_plain(keep), ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def load(mode, question, live=True):
    """The recorded answer with fresh live counts, or None."""
    path = CACHE / f"{_key(mode, question)}.json"
    if not path.exists():
        return None
    res = json.loads(path.read_text(encoding="utf-8"))
    res["cached"] = res.get("recorded", "").replace("T", " ")
    res["sources"] = [tuple(s) if isinstance(s, list) else s for s in res.get("sources", [])]
    cards = res.get("stations") or []
    if cards and live:
        try:
            feed = hybrid.ns.fetch_stations()
            res["stations"] = hybrid.live_cards([c["sno"] for c in cards], feed,
                                                {c["sno"]: c.get("distance_m") for c in cards})
        except Exception as exc:  # keep the recorded cards without counts
            res["live_error"] = f"{type(exc).__name__}: {exc}"
    if res.get("place_card"):  # photo paths and links are rebuilt on this computer
        import graph_route
        b = next((x for x in hybrid.buildings() if x["name"] == res["place_card"]["name"]), None)
        if b:
            res["place_card"] = graph_route.place_card(b)
    return res


def recorded():
    return sorted(CACHE.glob("*.json")) if CACHE.exists() else []
