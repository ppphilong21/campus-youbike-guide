"""Show what GraphRAG local search finds for a question, step by step.

Usage, from the repo folder:
  python scripts/debug_retrieval.py graphrag_test "How much does a one-hour ride on a YouBike 2.0E cost?"
  python scripts/debug_retrieval.py graphrag "..." --no-llm     (skips step 3, takes a few seconds)

1. Ranks every entity by similarity to the question, embedding them again with the
   embedding model through Ollama. This does not use the vector store.
2. Runs the same vector search GraphRAG uses (LanceDB table entity_description) and
   checks that the stored vectors match freshly computed ones.
3. Runs local search and lists the entities, reports and source texts in its context.

How to read it:
- 1 finds the right entities but 2 does not: the vector store is the problem.
- 1 and 2 are right but 3 has no source text with the answer: the context step is the problem.
- 3 has the right source text and the answer is still wrong: the model is the problem.
- 1 does not find the right entities either: extraction missed them, or the embedding model
  does not match the question well.
"""
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
TOP = 20  # local search looks at top_k_entities (10) x oversample (2) = 20 entities


def settings(root):
    with open(root / "settings.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    model_id = (cfg.get("local_search") or {}).get("embedding_model_id", "default_embedding_model")
    m = cfg["embedding_models"][model_id]
    return m["model"], m.get("api_base", "http://localhost:11434").rstrip("/")


def embed(texts, model, base):
    out = []
    for i in range(0, len(texts), 32):
        r = requests.post(f"{base}/api/embed", json={"model": model, "input": texts[i:i + 32]}, timeout=600)
        r.raise_for_status()
        out.extend(r.json()["embeddings"])
    v = np.array(out, dtype=np.float32)
    return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-12)


def short(text, n=110):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 3] + "..."


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2:
        raise SystemExit(__doc__)
    root, question = Path(args[0]), " ".join(args[1:])
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    ents = pd.read_parquet(root / "output" / "entities.parquet")
    title_of = dict(zip(ents["id"], ents["title"]))
    model, base = settings(root)
    print(f"{len(ents)} entities in {root}. Embedding model: {model}\n")

    # 1. Fresh similarity, no vector store
    texts = (ents["title"].astype(str) + ":" + ents["description"].fillna("").astype(str)).tolist()
    fresh = embed(texts, model, base)
    q = embed([question], model, base)[0]
    sims = fresh @ q
    order = np.argsort(-sims)
    print(f"1. Most similar entities, computed directly (top {TOP}):")
    for rank, i in enumerate(order[:TOP], 1):
        print(f"  {rank:2}. {sims[i]:.3f}  {ents['title'].iat[i]:<34} {short(ents['description'].iat[i], 70)}")

    # 2. The vector store GraphRAG searches
    import lancedb

    table = lancedb.connect(str(root / "output" / "lancedb")).open_table("entity_description")
    stored = table.to_pandas()
    vec = np.stack(stored["vector"].to_numpy()).astype(np.float32)
    print(f"\n2. Vector store: {len(stored)} rows, {vec.shape[1]} dimensions, "
          f"{int(np.isnan(vec).any(axis=1).sum())} rows with NaN")
    fresh_by_id = dict(zip(ents["id"], fresh))
    agree = [float(v @ fresh_by_id[i] / max(np.linalg.norm(v), 1e-12))
             for i, v in zip(stored["id"], vec) if i in fresh_by_id]
    if agree:
        print(f"   stored vs fresh vectors: cosine min {min(agree):.3f}, mean {np.mean(agree):.3f} "
              "(both should be close to 1.000)")
    hits = table.search(q, vector_column_name="vector").limit(TOP).to_list()
    print(f"   GraphRAG's search for the question (top {TOP}):")
    for rank, h in enumerate(hits, 1):
        print(f"  {rank:2}. dist {h['_distance']:.3f}  {title_of.get(h['id'], h['id'])}")

    if "--no-llm" in sys.argv:
        return

    # 3. The real local search
    sys.path.insert(0, str(REPO / "app"))
    from graph_query import run_query  # noqa: E402

    print("\n3. Local search (calls the model, takes a minute or two)...")
    res = run_query(question, "local", root=root)
    ctx = res["context"] if isinstance(res["context"], dict) else {}
    size = 0
    for kind in ("entities", "relationships", "reports", "sources"):
        table = ctx.get(kind)
        if table is None or len(table) == 0:
            print(f"\n   {kind}: none")
            continue
        size += len(table.to_csv(index=False))
        print(f"\n   {kind} ({len(table)}):")
        for row in table.to_dict("records"):
            if kind == "entities":
                print(f"     {row.get('entity', '')}")
            elif kind == "relationships":
                print(f"     {row.get('source', '')} -> {row.get('target', '')}")
            elif kind == "reports":
                print(f"     [{row.get('id', '')}] {short(row.get('title', ''), 90)}")
            else:
                lines = [ln for ln in str(row.get("text", "")).splitlines() if ln.strip()]
                head = next((ln for ln in lines if not ln.startswith("Source:")), lines[0] if lines else "")
                print(f"     [{row.get('id', '')}] {short(head, 90)}")
    print(f"\n   Context size: about {size // 4} tokens. Time: {res['seconds']:.0f} s")
    print(f"\nAnswer:\n{res['answer']}")


if __name__ == "__main__":
    main()
