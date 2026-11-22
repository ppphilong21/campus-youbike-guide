"""Ask every evaluation question in each retrieval mode and save the answers.

Results go to eval/results/<tag>.jsonl, one line per (question, mode). The script can be
stopped at any time (Ctrl+C) and started again with the same command: it skips what is
already done and retries answers that ended in an error.

Examples (from the project folder, with the venv active and Ollama running):
  python eval/run_eval.py --tag main --modes basic,local,hybrid
  python eval/run_eval.py --tag main --modes global,drift --types multihop,global
  python eval/run_eval.py --tag 8b --variant 8b --modes local,hybrid
  python eval/run_eval.py --tag noreports --variant noreports --modes local
  python eval/run_eval.py --tag try --modes local --ids F01,M01 --dry-run
  python eval/run_eval.py --plan full          # all of the above, one step after another

Variants change settings for these queries only; settings.yaml and the index stay as they are:
  default    the settings in settings.yaml
  8b         answers written by qwen3:8b instead of the 4B model (run `ollama pull qwen3:8b` first)
  noreports  local search without community reports (community_prop 0)
"""
import argparse
import csv
import datetime as dt
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

MODES = ("basic", "local", "hybrid", "global", "drift")
TYPES = ("fact", "multihop", "global", "station", "unanswerable", "multilingual")
VARIANTS = {
    "default": {},
    "8b": {"completion_models": {"default_completion_model": {"model": "qwen3:8b"}}},
    "noreports": {"local_search": {"community_prop": 0.0}},
}


def load_questions(path, ids=None, types=None):
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if ids:
        rows = [r for r in rows if r["id"] in ids]
    if types:
        rows = [r for r in rows if r["type"] in types]
    return rows


def done_keys(path):
    """(id, mode) pairs that already have an answer without an error."""
    keys = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue  # a line cut by a crash
            if not rec.get("error"):
                keys.add((rec["id"], rec["mode"]))
    return keys


class DocLookup:
    """Text chunk id in the search context -> input file name, from the index tables."""

    def __init__(self, root):
        import pandas as pd

        out = Path(root) / "output"
        docs = pd.read_parquet(out / "documents.parquet", columns=["id", "title"])
        units = pd.read_parquet(out / "text_units.parquet", columns=["human_readable_id", "document_id"])
        title = dict(zip(docs["id"], docs["title"]))
        self.by_chunk = {str(h): Path(str(title.get(d, ""))).stem for h, d in
                         zip(units["human_readable_id"], units["document_id"])}

    def files(self, context):
        rows = context.get("sources") if isinstance(context, dict) else None
        if rows is None or not hasattr(rows, "to_dict"):
            return []
        seen = []
        for r in rows.to_dict("records"):
            name = self.by_chunk.get(str(r.get("id")), "")
            if name and name not in seen:
                seen.append(name)
        return seen


def count(context, kind):
    rows = context.get(kind) if isinstance(context, dict) else None
    return int(len(rows)) if rows is not None and hasattr(rows, "__len__") else 0


def ask(row, mode, args, overrides, lookup):
    import hybrid

    rec = {"tag": args.tag, "variant": args.variant, "id": row["id"], "type": row["type"], "lang": row["lang"],
           "mode": mode, "question": row["question"], "response_type": args.response_type,
           "time": dt.datetime.now().isoformat(timespec="seconds")}
    start = time.perf_counter()
    try:
        res = hybrid.answer(row["question"], mode, root=args.root, response_type=args.response_type,
                            overrides=overrides, live=False)
        ctx = res.get("context")
        graph = res.get("graph_context") or {}
        rec.update(
            answer=res.get("answer", ""),
            seconds=round(res.get("seconds") or (time.perf_counter() - start), 1),
            place=res.get("place"),
            stations=[{"sno": c["sno"], "name": c["name"], "distance_m": c["distance_m"]} for c in res.get("stations", [])],
            files=lookup.files(ctx),
            n_entities=count(ctx, "entities"), n_relationships=count(ctx, "relationships"),
            n_reports=count(ctx, "reports"), n_chunks=count(ctx, "sources"),
            entities=(graph.get("entities") or [])[:30],
            error=None,
        )
    except KeyboardInterrupt:
        raise
    except Exception as exc:  # keep going; the error is saved and retried on the next run
        rec.update(answer="", seconds=round(time.perf_counter() - start, 1),
                   error=f"{type(exc).__name__}: {exc}", trace=traceback.format_exc()[-1500:])
    return rec


# --plan full: the whole evaluation in one command, step by step (each step resumes on its own)
PLANS = {
    "full": [
        {"tag": "main", "modes": "basic,local,hybrid", "types": ""},
        {"tag": "main", "modes": "global", "types": "multihop,global"},
        {"tag": "main", "modes": "drift", "types": "global"},
        {"tag": "noreports", "variant": "noreports", "modes": "local", "types": "multihop,station"},
        {"tag": "8b", "variant": "8b", "modes": "local", "types": "multihop,station"},
    ],
}


def run_step(args, p):
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    bad = [m for m in modes if m not in MODES]
    if bad:
        p.error(f"unknown mode(s) {bad}; choose from {MODES}")
    types = {t.strip() for t in args.types.split(",") if t.strip()}
    if types - set(TYPES):
        p.error(f"unknown type(s) {sorted(types - set(TYPES))}; choose from {TYPES}")
    ids = {i.strip() for i in args.ids.split(",") if i.strip()}

    questions = load_questions(args.questions, ids, types)
    out_path = ROOT / "eval" / "results" / f"{args.tag}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = done_keys(out_path)
    # one mode at a time, so a stopped run still has complete columns to compare
    todo = [(q, m) for m in modes for q in questions if (q["id"], m) not in done]

    print(f"{len(questions)} questions x {len(modes)} modes ({','.join(modes)}); {len(todo)} to run, "
          f"{len(questions) * len(modes) - len(todo)} already done -> {out_path}")
    print(f"variant {args.variant}, root {args.root}, response type '{args.response_type}'")
    if args.dry_run:
        for q, m in todo:
            print(f"  {m:7} {q['id']}  {q['question'][:70]}")
        return

    lookup = DocLookup(args.root)
    overrides = VARIANTS[args.variant]
    times = {}
    started = time.perf_counter()
    with open(out_path, "a", encoding="utf-8") as f:
        for n, (q, mode) in enumerate(todo, 1):
            rec = ask(q, mode, args, overrides, lookup)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            if not rec["error"]:
                times.setdefault(mode, []).append(rec["seconds"])
            left = [m for _, m in todo[n:]]
            avg = {m: sum(v) / len(v) for m, v in times.items()}
            fallback = sum(sum(v) for v in times.values()) / max(1, sum(len(v) for v in times.values()))
            eta = sum(avg.get(m, fallback) for m in left) / 60
            status = "ERROR " + rec["error"][:80] if rec["error"] else f"{rec['seconds']:.0f}s"
            print(f"[{n}/{len(todo)}] {mode:7} {q['id']}  {status}  | elapsed "
                  f"{(time.perf_counter() - started) / 60:.0f} min, about {eta:.0f} min left", flush=True)

    missing = [(q["id"], m) for m in modes for q in questions if (q["id"], m) not in done_keys(out_path)]
    print(f"finished. Answers in {out_path}." + (f" {len(missing)} ended in an error: run the same command "
                                                 "again to retry them." if missing else ""))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--plan", choices=sorted(PLANS), help="run a fixed list of steps (see PLANS); no --tag needed")
    p.add_argument("--tag", help="name of the results file, e.g. main")
    p.add_argument("--modes", default="basic,local,hybrid", help=f"comma list from {','.join(MODES)}")
    p.add_argument("--types", default="", help=f"only these question types: {','.join(TYPES)}")
    p.add_argument("--ids", default="", help="only these question ids, e.g. F01,M03")
    p.add_argument("--variant", default="default", choices=sorted(VARIANTS))
    p.add_argument("--root", default=str(ROOT / "graphrag"), help="GraphRAG folder (default graphrag)")
    p.add_argument("--questions", default=str(ROOT / "eval" / "questions.csv"))
    p.add_argument("--response-type", default="Single Paragraph",
                   help='answer length GraphRAG asks for (the app uses "Multiple Paragraphs")')
    p.add_argument("--dry-run", action="store_true", help="list what would run, then stop")
    args = p.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # Vietnamese/Chinese text in a non-UTF-8 console
    if not args.plan and not args.tag:
        p.error("give --tag (or --plan full)")
    if not (Path(args.root) / "output" / "entities.parquet").exists():
        p.error(f"no index found in {args.root}/output; run graphrag index first")

    if not args.plan:
        run_step(args, p)
        return
    steps = PLANS[args.plan]
    for i, step in enumerate(steps, 1):
        step_args = argparse.Namespace(**{**vars(args), "variant": "default", **step})
        print(f"\n=== step {i}/{len(steps)}: tag {step_args.tag}, variant {step_args.variant} ===")
        run_step(step_args, p)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped. Run the same command again to continue where it left off.")
