"""Score the answers saved by run_eval.py and write the result tables.

  python eval/score_eval.py eval/results/main.jsonl eval/results/8b.jsonl eval/results/noreports.jsonl
  python eval/score_eval.py eval/results/main.jsonl --show M01,U02   # print those answers side by side

Writes, next to the first results file:
  per_answer.csv  one row per answer with every score
  summary.csv     one row per system (mode, plus the variant if it is not the default)
  summary.md      the same tables as Markdown, for the report and the slides
  summary.html    charts of the same numbers (open in a browser; no extra packages needed)

Scores (automatic, no judge model):
  accuracy   answerable question: every key fact appears in the answer;
             unanswerable question: the answer says the data does not contain it
  recall     share of key facts found (answerable questions only)
  refusal    answerable question answered with "not in the data" and no key fact (a miss)
  file hit   the search context contains a text chunk from the expected input file
             (n/a for global search, which reads community reports, not chunks)
  seconds    time for the whole answer on this computer
Key facts: ";" separates facts that must all appear, "|" separates accepted spellings.
"""
import argparse
import csv
import json
import re
import statistics
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TYPES = ("fact", "multihop", "global", "station", "unanswerable", "multilingual")
MODE_ORDER = ("basic", "local", "hybrid", "global", "drift")

REFUSAL = (
    # English
    "not in the data", "not in the provided", "does not contain", "doesn't contain", "no information",
    "not provided", "not mention", "no mention", "not specified", "does not specify", "doesn't specify",
    "do not have", "don't have", "does not have", "doesn't have", "cannot find", "can't find",
    "could not find", "unable to", "not available", "i don't know", "i do not know", "not included",
    "does not include", "doesn't include", "no data", "not enough information", "insufficient",
    "no specific", "not stated", "not able to", "cannot be determined", "can't be determined",
    "not possible to determine",
    # Vietnamese
    "không có thông tin", "không có dữ liệu", "không được đề cập", "không đề cập", "không tìm thấy",
    "không rõ", "không biết", "chưa có thông tin",
    # Chinese
    "未提及", "沒有提到", "没有提到", "沒有相關", "没有相关", "無法", "无法", "未提供", "不清楚", "不知道",
    "資料中沒有", "数据中没有", "資料未",
)


def norm(text):
    s = unicodedata.normalize("NFKC", str(text or "")).lower()
    s = re.sub(r"[-_\u2010-\u2015]", " ", s)                              # dashes -> space
    s = re.sub(r"\b([ap])\.m\.?", r"\1m", s)                             # 9 p.m. -> 9 pm
    s = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", s)                     # 3,000 -> 3000
    s = re.sub(r"(?:nt\$|ntd|twd)\s*(?=\d)", "nt$", s)                  # NT$ 40, NTD40 -> nt$40
    s = re.sub(r"(?<![\w$])(\d+(?:\.\d+)?)\s*(?:new taiwan dollars?|nt dollars?|ntd|twd|dollars?|元)",
               r"nt$\1", s)                                              # 40 NTD, 40元 -> nt$40
    return re.sub(r"\s+", " ", s).strip()


def _pattern(alt):
    a = norm(alt)
    if not a:
        return None
    rx = re.escape(a)
    if a[0].isdigit():
        rx = r"(?<![\d.:])" + rx
    elif "a" <= a[0] <= "z":
        rx = r"(?<![a-z])" + rx
    if a[-1].isdigit():
        rx += r"(?![\d])"
    elif "a" <= a[-1] <= "z" and len(a) <= 3:  # short words (no, IB, RB) must stand alone;
        rx += r"(?![a-z])"                      # longer ones may be a stem ("not subsidi")
    return re.compile(rx)


def facts(key_facts):
    """'a|b;c' -> [['a', 'b'], ['c']]"""
    return [[alt.strip() for alt in group.split("|") if alt.strip()]
            for group in str(key_facts or "").split(";") if group.strip()]


def found(answer, alternatives):
    text = norm(answer)
    return any(p.search(text) for p in map(_pattern, alternatives) if p)


def refuses(answer):
    text = norm(answer)
    return any(norm(p) in text for p in REFUSAL)


def file_hit(expected, files):
    want = [f.strip() for f in str(expected or "").split(";") if f.strip()]
    if not want or not files:
        return None
    for w in want:
        if w == "station files":
            if any(f.startswith("station_") for f in files):
                return True
        elif w in files:
            return True
    return False


def system_name(rec):
    v = rec.get("variant") or "default"
    return rec["mode"] if v == "default" else f"{rec['mode']}+{v}"


def load(paths):
    """Latest answer without an error per (system, question)."""
    best = {}
    for path in paths:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("error"):
                continue
            best[(system_name(rec), rec["id"])] = rec
    return best


def score(rec, q):
    groups = facts(q["key_facts"])
    answer = rec.get("answer", "")
    unanswerable = q["key_facts"].strip() == "NOT_IN_DATA"
    row = {"system": system_name(rec), "mode": rec["mode"], "variant": rec.get("variant", "default"),
           "id": q["id"], "type": q["type"], "lang": q["lang"], "seconds": rec.get("seconds"),
           "n_chunks": rec.get("n_chunks"), "n_entities": rec.get("n_entities"),
           "n_reports": rec.get("n_reports"), "files": ";".join(rec.get("files") or [])}
    said_no = refuses(answer)
    if unanswerable:
        row.update(facts_found="", facts_total="", recall="", accuracy=int(said_no), refusal="", file_hit="")
    else:
        hits = [found(answer, g) for g in groups]
        n = sum(hits)
        row.update(facts_found=n, facts_total=len(groups), recall=round(n / len(groups), 3) if groups else "",
                   accuracy=int(bool(groups) and n == len(groups)), refusal=int(said_no and n == 0))
        h = file_hit(q["source_files"], rec.get("files"))
        row["file_hit"] = "" if h is None else int(h)
    return row


def mean(values):
    vals = [float(v) for v in values if v not in ("", None)]
    return sum(vals) / len(vals) if vals else None


def pct(v):
    return "–" if v is None else f"{100 * v:.0f}%"


def secs(v):
    return "–" if v is None else f"{v:.0f}"


def order(systems):
    def key(s):
        mode, _, variant = s.partition("+")
        return (bool(variant), MODE_ORDER.index(mode) if mode in MODE_ORDER else 9, variant)
    return sorted(systems, key=key)


def summarise(rows):
    out = []
    for system in order({r["system"] for r in rows}):
        rs = [r for r in rows if r["system"] == system]
        answerable = [r for r in rs if r["type"] != "unanswerable"]
        unans = [r for r in rs if r["type"] == "unanswerable"]
        times = [float(r["seconds"]) for r in rs if r["seconds"] not in ("", None)]
        line = {"system": system, "answers": len(rs),
                "accuracy": mean(r["accuracy"] for r in rs),
                "recall": mean(r["recall"] for r in answerable),
                "unanswerable_correct": mean(r["accuracy"] for r in unans),
                "refusal_rate": mean(r["refusal"] for r in answerable),
                "file_hit": mean(r["file_hit"] for r in answerable),
                "median_seconds": statistics.median(times) if times else None,
                "mean_seconds": mean(times)}
        for t in TYPES:
            line[f"acc_{t}"] = mean(r["accuracy"] for r in rs if r["type"] == t)
            line[f"n_{t}"] = sum(1 for r in rs if r["type"] == t)
        out.append(line)
    return out


def ablation(rows):
    """Each variant against its base mode on exactly the same questions."""
    variants = [s for s in order({r["system"] for r in rows}) if "+" in s]
    if not variants:
        return []
    by = {(r["system"], r["id"]): r for r in rows}
    out = ["", "## Ablation (same questions as the base mode)", "",
           "| Change | Questions | Accuracy base → variant | Recall base → variant | Median s base → variant |",
           "| --- | ---: | :---: | :---: | :---: |"]
    for v in variants:
        base = v.split("+")[0]
        ids = [i for (s, i) in by if s == v and (base, i) in by]
        if not ids:
            continue
        pair = [(by[(base, i)], by[(v, i)]) for i in ids]

        def med(rs):
            t = [float(r["seconds"]) for r in rs if r["seconds"] not in ("", None)]
            return statistics.median(t) if t else None

        b, w = [p[0] for p in pair], [p[1] for p in pair]
        out.append(f"| {v} | {len(ids)} | {pct(mean(r['accuracy'] for r in b))} → {pct(mean(r['accuracy'] for r in w))} "
                   f"| {pct(mean(r['recall'] for r in b))} → {pct(mean(r['recall'] for r in w))} "
                   f"| {secs(med(b))} → {secs(med(w))} |")
    return out


def markdown(summary, rows, sources):
    lines = ["# Evaluation results", "", "Files: " + ", ".join(f"`{Path(s).name}`" for s in sources), "",
             "## Overall", "",
             "| System | Answers | Accuracy | Key-fact recall | Unanswerable correct | False refusals "
             "| File hit | Median s | Mean s |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for s in summary:
        lines.append(f"| {s['system']} | {s['answers']} | {pct(s['accuracy'])} | {pct(s['recall'])} | "
                     f"{pct(s['unanswerable_correct'])} | {pct(s['refusal_rate'])} | {pct(s['file_hit'])} | "
                     f"{secs(s['median_seconds'])} | {secs(s['mean_seconds'])} |")
    lines += ["", "## Accuracy by question type", "",
              "| System | " + " | ".join(TYPES) + " |", "| --- |" + " ---: |" * len(TYPES)]
    for s in summary:
        cells = [f"{pct(s[f'acc_{t}'])} ({s[f'n_{t}']})" if s[f"n_{t}"] else "–" for t in TYPES]
        lines.append(f"| {s['system']} | " + " | ".join(cells) + " |")
    lines += ablation(rows)
    systems = [s["system"] for s in summary]
    lines += ["", "## Per question", "", "✓ all key facts (or a correct refusal), ◐ some, ✗ none, – not run", "",
              "| Question | " + " | ".join(systems) + " |", "| --- |" + " :---: |" * len(systems)]
    by = {(r["system"], r["id"]): r for r in rows}
    for qid in sorted({r["id"] for r in rows}, key=lambda i: ("FMGSUL".find(i[0]), i)):
        cells = []
        for system in systems:
            r = by.get((system, qid))
            if not r:
                cells.append("–")
            elif r["accuracy"]:
                cells.append("✓")
            elif r["recall"] not in ("", None) and float(r["recall"]) > 0:
                cells.append("◐")
            else:
                cells.append("✗")
        lines.append(f"| {qid} | " + " | ".join(cells) + " |")
    lines += ["", "Accuracy counts answerable questions with every key fact present and unanswerable questions "
              "answered with 'not in the data'. Key facts are matched as text (case, hyphens, thousands "
              "separators and NT$ spellings normalised), so check a sample by hand with `--show`.", ""]
    return "\n".join(lines)


def show(ids, best, questions):
    for qid in ids:
        q = questions.get(qid)
        if not q:
            print(f"{qid}: no such question")
            continue
        print("=" * 100)
        print(f"{qid} [{q['type']}] {q['question']}")
        print(f"reference: {q['reference_answer']}")
        print(f"key facts: {q['key_facts']}")
        for system in order({s for s, i in best if i == qid}):
            rec = best[(system, qid)]
            r = score(rec, q)
            print(f"\n--- {system}  accuracy {r['accuracy']}  recall {r['recall']}  {rec.get('seconds')} s  "
                  f"files {r['files'] or '-'}")
            print(rec.get("answer", "").strip())
        print()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("results", nargs="+", help="one or more eval/results/<tag>.jsonl files")
    p.add_argument("--questions", default=str(ROOT / "eval" / "questions.csv"))
    p.add_argument("--show", default="", help="print the answers to these question ids, e.g. M01,U02")
    p.add_argument("--out", default="", help="folder for the tables (default: next to the first results file)")
    args = p.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    with open(args.questions, encoding="utf-8", newline="") as f:
        questions = {r["id"]: r for r in csv.DictReader(f)}
    best = load(args.results)
    if args.show:
        show([i.strip() for i in args.show.split(",") if i.strip()], best, questions)
        return

    rows = [score(rec, questions[qid]) for (system, qid), rec in best.items() if qid in questions]
    systems = order({r["system"] for r in rows})
    rows.sort(key=lambda r: (systems.index(r["system"]), "FMGSUL".find(r["id"][0]), r["id"]))
    summary = summarise(rows)
    out = Path(args.out) if args.out else Path(args.results[0]).parent
    out.mkdir(parents=True, exist_ok=True)

    with open(out / "per_answer.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(out / "summary.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0]))
        w.writeheader()
        for s in summary:
            w.writerow({k: (round(v, 3) if isinstance(v, float) else v) for k, v in s.items()})
    md = markdown(summary, rows, args.results)
    (out / "summary.md").write_text(md, encoding="utf-8")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import charts

    (out / "summary.html").write_text(charts.page(summary), encoding="utf-8")

    print(md.split("## Per question")[0].strip())
    print(f"\nWrote {out / 'summary.md'} (tables), {out / 'summary.html'} (charts, open in a browser), "
          f"{out / 'summary.csv'} and {out / 'per_answer.csv'}")


if __name__ == "__main__":
    main()
