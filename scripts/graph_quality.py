"""Measure how clean the knowledge graph that the LLM extracted is.

Checks on graphrag/output (no model needed):
- entity types outside the schema in settings.yaml (the model made up a type or misspelled one)
- duplicate entities: titles that are the same after removing case, spaces, underscores and
  punctuation (for example IC CARD and IC_CARD)
- entities with no relationship at all
- relationships from an entity to itself

Usage: python scripts/graph_quality.py [graphrag_root] [--out eval/results/graph_quality.md]
"""
import argparse
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def schema_types(root):
    text = (Path(root) / "settings.yaml").read_text(encoding="utf-8")
    m = re.search(r"entity_types:\s*\[([^\]]*)\]", text)
    return {t.strip().upper() for t in m.group(1).split(",")} if m else set()


def key(title):
    t = re.sub(r"[\W_]+", " ", str(title).upper())
    t = re.sub(r"\bYOUBIKE ?2 ?0\b", "YOUBIKE2.0", t)
    return " ".join(t.split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=str(ROOT / "graphrag"))
    ap.add_argument("--out", default=str(ROOT / "eval" / "results" / "graph_quality.md"))
    args = ap.parse_args()
    out = Path(args.root) / "output"
    ents = pd.read_parquet(out / "entities.parquet")
    rels = pd.read_parquet(out / "relationships.parquet")
    schema = schema_types(args.root)
    ents["T"] = ents["type"].fillna("").str.upper().str.replace(" ", "_")

    by_type = ents["T"].value_counts()
    outside = ents[~ents["T"].isin(schema)]
    groups = defaultdict(list)
    for t in ents["title"]:
        groups[key(t)].append(t)
    dups = {k: v for k, v in groups.items() if len(v) > 1}
    isolated = ents[ents["degree"].fillna(0) == 0]
    loops = rels[rels["source"] == rels["target"]]

    lines = [
        "# Knowledge graph quality",
        "",
        f"Index: `{Path(args.root).name}/output`. {len(ents)} entities, {len(rels)} relationships, "
        f"{len(schema)} entity types in the schema (`settings.yaml`).",
        "",
        "| Check | Count | Share |",
        "| --- | ---: | ---: |",
        f"| Entities with a type outside the schema | {len(outside)} | {len(outside) / len(ents):.0%} |",
        f"| Groups of duplicate entities (same title once spacing and punctuation are ignored) | {len(dups)} | "
        f"{sum(len(v) for v in dups.values())} entities |",
        f"| Entities with no relationship | {len(isolated)} | {len(isolated) / len(ents):.0%} |",
        f"| Relationships from an entity to itself | {len(loops)} | {len(loops) / max(1, len(rels)):.0%} |",
        "",
        "## Entities per type",
        "",
        "| Type | In schema | Entities |",
        "| --- | --- | ---: |",
    ]
    lines += [f"| {t.lower() or '(none)'} | {'yes' if t in schema else '**no**'} | {n} |" for t, n in by_type.items()]
    lines += ["", "## Types outside the schema", "", "| Type | Entities |", "| --- | --- |"]
    for t, g in outside.groupby("T"):
        lines.append(f"| {t.lower()} | " + ", ".join(sorted(g["title"]))[:400] + " |")
    lines += ["", "## Duplicate entities", "", "| Same entity written as |", "| --- |"]
    lines += ["| " + " · ".join(sorted(v)) + " |" for v in sorted(dups.values(), key=lambda v: -len(v))]
    lines += ["", "Duplicates are only the exact cases above; near-duplicates with different words (for example "
                  "YOUBIKE2.0_NTUST_MAIN_GATE and NTUST(MAIN GATE) STATION) need a person to judge.", ""]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:12]))
    print(f"\nwritten to {args.out}")


if __name__ == "__main__":
    main()
