r"""Record bike counts for the campus stations. Meant to run every 15 minutes.

Appends one row per campus station to data/raw/snapshots.csv:
time, sno, bikes (sbi), free_docks (bemp), act, feed_update_time (mday)

Uses absolute paths, so Windows Task Scheduler can start it from any folder.
Errors are written to data/raw/snapshot_errors.log instead of stopping the schedule.

Windows Task Scheduler (run once in PowerShell, from the repo folder; the folder path
must not contain spaces, e.g. C:\Projects\campus-youbike-guide):
  schtasks /Create /SC MINUTE /MO 15 /TN YouBikeSnapshot /TR "$PWD\.venv\Scripts\pythonw.exe $PWD\scripts\snapshot.py"
Run it once now:     schtasks /Run /TN YouBikeSnapshot
Stop it later with:  schtasks /Delete /TN YouBikeSnapshot /F
"""
import csv
import datetime as dt
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
RAW = os.path.join(ROOT, "data", "raw")
sys.path.insert(0, HERE)


def main():
    import nearest_station as ns

    os.makedirs(RAW, exist_ok=True)
    with open(os.path.join(ROOT, "data", "stations_campus.csv"), encoding="utf-8") as f:
        wanted = {r["sno"] for r in csv.DictReader(f)}
    stations = ns.fetch_stations()
    now = dt.datetime.now().isoformat(timespec="minutes")
    path = os.path.join(RAW, "snapshots.csv")
    new_file = not os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["time", "sno", "bikes", "free_docks", "act", "feed_update_time"])
        n = 0
        for s in stations:
            if s["sno"] in wanted:
                w.writerow([now, s["sno"], s.get("sbi", ""), s.get("bemp", ""), s.get("act", ""), s.get("mday", "")])
                n += 1
    return n


if __name__ == "__main__":
    try:
        count = main()
        print(f"Saved {count} stations")
    except Exception:
        os.makedirs(RAW, exist_ok=True)
        with open(os.path.join(RAW, "snapshot_errors.log"), "a", encoding="utf-8") as f:
            f.write(f"--- {dt.datetime.now().isoformat(timespec='seconds')}\n{traceback.format_exc()}\n")
        raise
