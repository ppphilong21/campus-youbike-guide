"""Summarise GraphRAG's model cache: calls, tokens, time and cut-off answers per step.

Every finished model call is saved in <root>/cache/<step>/ with its token counts and
duration, so this works after an index run and also while one is still running.

Usage:
  python scripts/cache_report.py                 # graphrag/
  python scripts/cache_report.py graphrag_test   # another root
  python scripts/cache_report.py graphrag_test --calls   # also list every call
  python scripts/cache_report.py graphrag_test --show-cut # print the start and end of cut-off answers

"cut" counts answers that stopped because they reached max_tokens (finish_reason
"length"). For extract_graph that means entities or relationships were lost: raise
max_tokens or lower the chunk size.
"""
import datetime as dt
import glob
import json
import os
import sys
from collections import defaultdict


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d["result"]["response"], d["result"].get("metrics") or {}
    except (OSError, ValueError, KeyError, TypeError):
        return None, None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_calls = "--calls" in sys.argv
    show_cut = "--show-cut" in sys.argv
    cut_texts = []
    root = args[0] if args else "graphrag"
    files = sorted(glob.glob(os.path.join(root, "cache", "*", "*")), key=os.path.getmtime)
    if not files:
        raise SystemExit(f"No cache files under {root}/cache")

    steps = defaultdict(lambda: {"calls": 0, "in": 0, "out": 0, "sec": 0.0, "cut": 0,
                                 "first": None, "last": None})
    if show_calls:
        print(f"{'finished':8}  {'step':24} {'end':7} {'in':>6} {'out':>5} {'sec':>6} {'out/s':>6}")
    for path in files:
        resp, metrics = load(path)
        if resp is None:
            continue
        step = os.path.basename(os.path.dirname(path))
        when = dt.datetime.fromtimestamp(os.path.getmtime(path))
        usage = resp.get("usage") or {}
        sec = float(metrics.get("compute_duration_seconds") or 0)
        s = steps[step]
        s["calls"] += 1
        s["in"] += usage.get("prompt_tokens") or 0
        s["out"] += usage.get("completion_tokens") or 0
        s["sec"] += sec
        s["first"] = s["first"] or when
        s["last"] = when
        choices = resp.get("choices") or []
        if not choices:  # embeddings
            continue
        end = choices[0].get("finish_reason") or ""
        if end == "length":
            s["cut"] += 1
            msg = choices[0].get("message") or {}
            cut_texts.append((when, step, msg.get("content") or resp.get("content") or ""))
        if show_calls:
            out = usage.get("completion_tokens") or 0
            rate = out / sec if sec else 0
            print(f"{when:%H:%M:%S}  {step:24} {end:7} {usage.get('prompt_tokens') or 0:>6} "
                  f"{out:>5} {sec:>6.0f} {rate:>6.1f}")

    if show_calls:
        print()
    print(f"{'step':24} {'calls':>5} {'cut':>4} {'in tok':>8} {'out tok':>8} {'minutes':>8} "
          f"{'min/call':>8} {'out/s':>6}  finished")
    total_sec = 0.0
    for step, s in sorted(steps.items(), key=lambda kv: kv[1]["first"]):
        total_sec += s["sec"]
        rate = s["out"] / s["sec"] if s["sec"] else 0
        per = s["sec"] / 60 / s["calls"] if s["calls"] else 0
        print(f"{step:24} {s['calls']:>5} {s['cut']:>4} {s['in']:>8} {s['out']:>8} {s['sec'] / 60:>8.1f} "
              f"{per:>8.1f} {rate:>6.1f}  {s['first']:%H:%M}-{s['last']:%H:%M}")
    print(f"\nModel time in total: {total_sec / 60:.1f} minutes")
    cut = sum(s["cut"] for s in steps.values())
    if show_cut:
        for when, step, text in cut_texts:
            print(f"\n--- cut answer, {step}, finished {when:%H:%M:%S}, {len(text)} characters ---")
            print(text[:400])
            print("   [...]")
            print(text[-700:])
    if cut:
        print(f"WARNING: {cut} answer(s) were cut off at max_tokens. See the docstring for the fix.")


if __name__ == "__main__":
    main()
