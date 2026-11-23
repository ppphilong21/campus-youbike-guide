"""Charts for the evaluation summary as one self-contained HTML page (inline SVG, no extra packages).

Called by score_eval.py; writes summary.html next to summary.md. Open it in a browser and take
screenshots for the slides. Light and dark mode follow the system setting.
"""
from html import escape

TYPES = ("fact", "multihop", "global", "station", "unanswerable", "multilingual", "suitability")
LIGHT_STEPS = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]  # 100..700

CSS = """
:root { --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781; --grid:#e1e0d9;
  --bar:#2a78d6; --empty:#f0efec;
  --b0:#cde2fb; --b1:#9ec5f4; --b2:#6da7ec; --b3:#3987e5; --b4:#256abf; --b5:#184f95; --b6:#0d366b;
  --t0:#0b0b0b; --t1:#0b0b0b; --t2:#0b0b0b; --t3:#ffffff; --t4:#ffffff; --t5:#ffffff; --t6:#ffffff; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --page:#0d0d0d; --surface:#1a1a19;
  --ink:#f0efec; --ink2:#c3c2b7; --grid:#2c2c2a; --bar:#3987e5; --empty:#262624;
  --b0:#0d366b; --b1:#184f95; --b2:#256abf; --b3:#3987e5; --b4:#6da7ec; --b5:#9ec5f4; --b6:#cde2fb;
  --t0:#ffffff; --t1:#ffffff; --t2:#ffffff; --t3:#ffffff; --t4:#0b0b0b; --t5:#0b0b0b; --t6:#0b0b0b; } }
:root[data-theme="dark"] { --page:#0d0d0d; --surface:#1a1a19; --ink:#f0efec; --ink2:#c3c2b7; --grid:#2c2c2a;
  --bar:#3987e5; --empty:#262624;
  --b0:#0d366b; --b1:#184f95; --b2:#256abf; --b3:#3987e5; --b4:#6da7ec; --b5:#9ec5f4; --b6:#cde2fb;
  --t0:#ffffff; --t1:#ffffff; --t2:#ffffff; --t3:#ffffff; --t4:#0b0b0b; --t5:#0b0b0b; --t6:#0b0b0b; }
* { box-sizing: border-box; }
body { margin:0; background:var(--page); color:var(--ink); font:14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 900px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 20px; margin: 0 0 4px; } p.note { color: var(--ink2); margin: 0 0 20px; }
section { background: var(--surface); border: 1px solid var(--grid); border-radius: 8px; padding: 16px; margin: 0 0 16px; }
h2 { font-size: 15px; margin: 0 0 2px; } .sub { color: var(--ink2); font-size: 13px; margin: 0 0 10px; }
svg { display: block; width: 100%; height: auto; overflow: visible; }
svg text { fill: var(--ink2); font-size: 12px; } svg .val { fill: var(--ink); }
svg .grid { stroke: var(--grid); stroke-width: 1; } svg .bar { fill: var(--bar); }
svg .bar:hover, svg .cell:hover { opacity: .85; }
"""


def _bar_path(x, y, w, h, r=4):
    """Bar anchored at x with a rounded data end on the right."""
    if w <= 0:
        return ""
    r = min(r, w, h / 2)
    return (f"M{x:.1f},{y:.1f} h{w - r:.1f} a{r},{r} 0 0 1 {r},{r} v{h - 2 * r:.1f} "
            f"a{r},{r} 0 0 1 {-r},{r} h{-(w - r):.1f} z")


def nice_max(v):
    """Round the scale up so the four gridline steps are round numbers of seconds."""
    for step in (5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600):
        if v <= 4 * step:
            return 4 * step
    return v


def bars(items, fmt, max_value):
    """Horizontal bar chart. items: [(label, value or None, tooltip)]."""
    label_w, plot_w, row_h, bar_h, top = 150, 600, 28, 16, 8
    height = top + row_h * len(items) + 24
    out = [f'<svg viewBox="0 0 {label_w + plot_w + 60} {height}" role="img">']
    for k in range(5):  # gridlines at 0, 25, 50, 75, 100 % of the scale
        x = label_w + plot_w * k / 4
        out.append(f'<line class="grid" x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{height - 20}"/>')
        out.append(f'<text x="{x:.1f}" y="{height - 4}" text-anchor="middle">{fmt(max_value * k / 4)}</text>')
    for i, (label, value, tip) in enumerate(items):
        y = top + i * row_h + (row_h - bar_h) / 2
        out.append(f'<text x="{label_w - 10}" y="{y + bar_h - 4}" text-anchor="end">{escape(label)}</text>')
        if value is None:
            out.append(f'<text x="{label_w + 6}" y="{y + bar_h - 4}">–</text>')
            continue
        w = plot_w * min(value, max_value) / max_value if max_value else 0
        out.append(f'<path class="bar" d="{_bar_path(label_w, y, w, bar_h)}"><title>{escape(tip)}</title></path>')
        out.append(f'<text class="val" x="{label_w + w + 6:.1f}" y="{y + bar_h - 4}">{fmt(value)}</text>')
    out.append("</svg>")
    return "".join(out)


def heatmap(summary, prefix="acc_"):
    """Accuracy by system (rows) and question type (columns), one blue ramp."""
    label_w, cell_w, cell_h, top = 150, 100, 34, 24
    width, height = label_w + cell_w * len(TYPES), top + cell_h * len(summary)
    out = [f'<svg viewBox="0 0 {width} {height}" role="img">']
    for j, t in enumerate(TYPES):
        out.append(f'<text x="{label_w + j * cell_w + cell_w / 2}" y="{top - 8}" text-anchor="middle">{t}</text>')
    for i, s in enumerate(summary):
        y = top + i * cell_h
        out.append(f'<text x="{label_w - 10}" y="{y + cell_h / 2 + 4}" text-anchor="end">{escape(s["system"])}</text>')
        for j, t in enumerate(TYPES):
            x = label_w + j * cell_w
            v, n = s.get(f"{prefix}{t}"), s.get(f"n_{t}", 0)
            if v is None:
                out.append(f'<rect x="{x + 1}" y="{y + 1}" width="{cell_w - 2}" height="{cell_h - 2}" rx="4" '
                           f'style="fill:var(--empty)"/><text x="{x + cell_w / 2}" y="{y + cell_h / 2 + 4}" '
                           f'text-anchor="middle">–</text>')
                continue
            b = min(6, max(0, round(v * 6)))
            tip = f"{s['system']}, {t}: {100 * v:.0f}% of {n} questions"
            out.append(f'<rect class="cell" x="{x + 1}" y="{y + 1}" width="{cell_w - 2}" height="{cell_h - 2}" '
                       f'rx="4" style="fill:var(--b{b})"><title>{escape(tip)}</title></rect>')
            out.append(f'<text x="{x + cell_w / 2}" y="{y + cell_h / 2 + 4}" text-anchor="middle" '
                       f'style="fill:var(--t{b})">{100 * v:.0f}% ({n})</text>')
    out.append("</svg>")
    return "".join(out) + legend()


def legend():
    """Scale for the heatmap: the seven ramp steps from 0% to 100%."""
    sw = "".join(f'<rect x="{40 + k * 28}" y="2" width="26" height="12" rx="2" style="fill:var(--b{k})"/>'
                 for k in range(7))
    return (f'<svg viewBox="0 0 300 18" style="max-width:300px;margin-top:8px" role="img" aria-label="scale">'
            f'<text x="34" y="12" text-anchor="end">0%</text>{sw}<text x="{40 + 7 * 28 + 4}" y="12">100%</text></svg>')


def _ok(r, hand):
    if hand and r.get("manual") not in ("", None):
        return int(float(r["manual"]) == 1)
    return int(r["accuracy"])


def ablation_items(rows, hand):
    """Base mode and each variant on exactly the same questions: (label, share right, median s)."""
    systems = {r["system"] for r in rows}
    variants = sorted(s for s in systems if "+" in s)
    groups = {}
    for v in variants:
        groups.setdefault(v.split("+")[0], []).append(v)
    if "hybrid" in systems and "hybrid2" in systems:
        groups.setdefault("hybrid", []).append("hybrid2")
    out = []
    for base, mine in sorted(groups.items()):
        ids = set.intersection(*[{r["id"] for r in rows if r["system"] == x} for x in [base] + mine])
        if not ids:
            continue
        for system in [base] + mine:
            rs = [r for r in rows if r["system"] == system and r["id"] in ids]
            times = sorted(float(r["seconds"]) for r in rs if r["seconds"] not in ("", None))
            med = times[len(times) // 2] if len(times) % 2 else (times[len(times) // 2 - 1] + times[len(times) // 2]) / 2
            out.append((system, sum(_ok(r, hand) for r in rs) / len(rs), med, len(ids)))
    return out


def page(summary, rows=None):
    hand = any(s.get("manual_n") for s in summary)
    key = "manual_correct" if hand else "accuracy"
    main = [s for s in summary if "+" not in s["system"]]
    name = lambda s: f"{s['system']} ({s['answers']})"
    acc = [(name(s), s[key], f"{s['system']}: {100 * (s[key] or 0):.0f}% of {s['answers']} answers") for s in main]
    rec = [(name(s), s["recall"], f"{s['system']}: key-fact recall {100 * (s['recall'] or 0):.0f}%") for s in main]
    sec = [(name(s), s["median_seconds"], f"{s['system']}: median {s['median_seconds'] or 0:.0f} s per answer")
           for s in main]
    abl = ablation_items(rows or [], hand)
    max_s = nice_max(max([v for _, v, _ in sec if v] or [1]))
    pct = lambda v: f"{100 * v:.0f}%"
    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        f"<title>Evaluation charts</title><style>{CSS}</style></head><body><main>",
        "<h1>Campus YouBike Guide: evaluation</h1>",
        "<p class='note'>" + ("Accuracy checked by hand; recall scored automatically from key facts. " if hand
                              else "Automatic key-fact scoring. ")
        + "Numbers in brackets are answer counts: global and DRIFT ran on the multi-hop and global questions "
        "only. Hover a bar or cell for details; the tables are in summary.md.</p>",
        "<section><h2>Accuracy by system</h2><p class='sub'>" + ("Answers fully right, checked by hand"
        if hand else "All key facts present, or a correct \"not in the data\" for unanswerable questions")
        + "</p>", bars(acc, pct, 1.0), "</section>",
        "<section><h2>Accuracy by question type</h2><p class='sub'>Share of questions answered fully, "
        "by type" + (", checked by hand" if hand else "") + "; – = not run for that system</p>",
        heatmap(main, "man_" if hand else "acc_"), "</section>",
        "<section><h2>Time per answer</h2><p class='sub'>Median seconds on the CPU laptop</p>",
        bars(sec, lambda v: f"{v:.0f}", max_s), "</section>",
        "<section><h2>Key-fact recall by system</h2><p class='sub'>Share of key facts found, answerable "
        "questions (automatic)</p>", bars(rec, pct, 1.0), "</section>",
    ]
    if abl:
        n = abl[0][3]
        parts += [
            f"<section><h2>Ablation: one change at a time</h2><p class='sub'>The same {n} questions (multi-hop "
            "and station); answers fully right" + (", checked by hand" if hand else "") + "</p>",
            bars([(a, v, f"{a}: {100 * v:.0f}% of {k} answers") for a, v, _, k in abl], pct, 1.0),
            "<p class='sub' style='margin-top:14px'>Median seconds per answer on the same questions</p>",
            bars([(a, m, f"{a}: median {m:.0f} s") for a, _, m, _ in abl], lambda v: f"{v:.0f}",
                 nice_max(max(m for _, _, m, _ in abl))),
            "</section>",
        ]
    parts.append("</main></body></html>")
    return "".join(parts)
