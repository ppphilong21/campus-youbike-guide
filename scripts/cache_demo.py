"""Record answers to the demo questions, so the app can show them at once during the pitch.

Each question is answered the normal way (Ollama must be running) and saved in
data/demo_cache/. Open the app as http://localhost:8501/?recorded=1: a recorded
question is shown immediately, labelled "Recorded answer", with live station counts.

Usage:
  python scripts/cache_demo.py                      # the questions in data/demo_questions.txt, Hybrid v2
  python scripts/cache_demo.py --modes hybrid2,basic
  python scripts/cache_demo.py --question "How do I get from IB to TR?"

data/demo_questions.txt: one question per line; lines starting with # are skipped.
"""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import demo_cache  # noqa: E402
import hybrid  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modes", default="hybrid2")
    ap.add_argument("--questions", default=str(ROOT / "data" / "demo_questions.txt"))
    ap.add_argument("--question", help="record only this question")
    ap.add_argument("--force", action="store_true", help="record again even if already recorded")
    args = ap.parse_args()

    if args.question:
        questions = [args.question]
    else:
        lines = Path(args.questions).read_text(encoding="utf-8").splitlines()
        questions = [q.strip() for q in lines if q.strip() and not q.lstrip().startswith("#")]
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    for mode in modes:
        for q in questions:
            if not args.force and demo_cache.load(mode, q, live=False):
                print(f"[{mode}] already recorded: {q}")
                continue
            t = time.perf_counter()
            res = hybrid.answer(q, mode, live=True)
            path = demo_cache.save(res)
            print(f"[{mode}] {time.perf_counter() - t:5.0f} s  {q}  -> {path.name}")


if __name__ == "__main__":
    main()
