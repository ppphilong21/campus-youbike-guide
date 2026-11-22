"""Run GraphRAG queries from Python and return the answer with the context it used.

Uses the same loading code as the `graphrag query` command (graphrag 3.3.0), so the
results match the command line. The context is kept because the app shows sources
and the evaluation (RAGAS) needs the retrieved text.

overrides: optional settings that replace values from settings.yaml for one query, in the
same nested shape, for the ablation without editing the file, e.g.
{"completion_models": {"default_completion_model": {"model": "qwen3:8b"}}}.

For offline tests only: set GRAPH_QUERY_STUB=1 to get a fixed answer without GraphRAG.
"""
import contextlib
import io
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAPHRAG_ROOT = Path(os.environ.get("GRAPHRAG_ROOT", ROOT / "graphrag"))
MODES = ("local", "global", "drift", "basic")


def _merge(base, extra):
    out = dict(base)
    for key, value in extra.items():
        out[key] = _merge(out[key], value) if isinstance(value, dict) and isinstance(out.get(key), dict) else value
    return out


@contextlib.contextmanager
def _with_overrides(q, overrides):
    """Make the CLI helpers load settings.yaml with `overrides` merged in."""
    if not overrides:
        yield
        return
    original = q.load_config

    def load_config(*args, **kwargs):
        kwargs["cli_overrides"] = _merge(kwargs.get("cli_overrides") or {}, overrides)
        return original(*args, **kwargs)

    q.load_config = load_config
    try:
        yield
    finally:
        q.load_config = original


def run_query(question, mode="local", community_level=2, response_type="Multiple Paragraphs", root=None,
              overrides=None):
    """Return {"mode", "answer", "context", "seconds"} for one GraphRAG query."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    start = time.perf_counter()
    if os.environ.get("GRAPH_QUERY_STUB"):
        answer = f"[stub {mode}] {question.splitlines()[0]}"
        context = {"sources": [{"id": "1", "text": "Source: stub\nThe Library is near the Main Gate."}]}
        return {"mode": mode, "answer": answer, "context": context, "seconds": time.perf_counter() - start}

    from graphrag.cli import query as q  # imported here so the app starts fast

    root = Path(root or GRAPHRAG_ROOT)
    with contextlib.redirect_stdout(io.StringIO()), _with_overrides(q, overrides):  # the CLI also prints
        if mode == "local":
            answer, context = q.run_local_search(None, root, community_level, response_type, False, question, False)
        elif mode == "global":
            answer, context = q.run_global_search(None, root, community_level, False, response_type, False, question, False)
        elif mode == "drift":
            answer, context = q.run_drift_search(None, root, community_level, response_type, False, question, False)
        else:
            answer, context = q.run_basic_search(None, root, response_type, False, question, False)
    if not isinstance(answer, str):
        answer = str(answer)
    return {"mode": mode, "answer": answer, "context": context, "seconds": time.perf_counter() - start}


def _rows(table):
    """Accept a pandas DataFrame or a list of dicts."""
    if table is None:
        return []
    if hasattr(table, "to_dict"):
        return table.to_dict("records")
    if isinstance(table, list):
        return [r for r in table if isinstance(r, dict)]
    return []


def context_sources(context, per_kind=5):
    """Flatten GraphRAG context into [(kind, title, text)] for display and evaluation.

    Column names differ by search method, so this looks for the usual ones.
    """
    if not isinstance(context, dict):
        return [("context", "", str(context))] if context else []
    out = []
    for kind in ("sources", "reports", "entities", "relationships", "claims"):
        for row in _rows(context.get(kind))[:per_kind]:
            text = next((str(row[c]) for c in ("text", "content", "description") if row.get(c)), "")
            title = next((str(row[c]) for c in ("title", "entity", "source", "id") if row.get(c) not in (None, "")), "")
            if kind == "relationships" and row.get("target"):
                title = f"{row.get('source', '')} -> {row['target']}"
            if text:
                out.append((kind, title, text))
    return out


def context_graph(context):
    """What a search put in the model's context, for the "how this answer was found" graph.

    Returns entity titles, (source, target) relationship pairs, report titles and the
    number of text chunks. Basic search has only text chunks; global search only reports.
    """
    if not isinstance(context, dict):
        return {"entities": [], "relationships": [], "reports": [], "sources": 0}
    ents = [str(r.get("entity") or r.get("title") or "") for r in _rows(context.get("entities"))]
    rels = [(str(r["source"]), str(r["target"])) for r in _rows(context.get("relationships"))
            if r.get("source") and r.get("target")]
    reports = [str(r.get("title", "")) for r in _rows(context.get("reports"))]
    return {"entities": [e for e in ents if e], "relationships": rels, "reports": reports,
            "sources": len(_rows(context.get("sources")))}


def context_texts(context):
    """Plain retrieved texts, the format RAGAS expects for retrieved_contexts."""
    return [text for _, _, text in context_sources(context, per_kind=20)]


if __name__ == "__main__":
    import sys

    q_text = " ".join(sys.argv[2:]) or "Which YouBike station is closest to the Library?"
    result = run_query(q_text, sys.argv[1] if len(sys.argv) > 1 else "local")
    print(result["answer"])
    print(f"\n[{result['mode']}, {result['seconds']:.1f} s, {len(context_sources(result['context']))} context items]")
