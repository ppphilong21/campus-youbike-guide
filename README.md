# Campus YouBike Guide (NTUST)

A question answering assistant that helps students choose a YouBike station around the
Taiwan Tech campus. Knowledge comes from GraphRAG over a small campus corpus, running on a
local model through Ollama. Live bike counts come straight from the Taipei YouBike API and
never pass through the language model.

## Quick start (Windows 11, PowerShell)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
ollama pull qwen3:4b
ollama pull bge-m3
```

## Pipeline

| Step | Command | Output |
| --- | --- | --- |
| Place coordinates | `python scripts/georef.py` | lat, lng in `data/buildings.csv` |
| Campus stations | `python scripts/fetch_stations.py` | `data/stations_campus.csv` |
| Bike count history | `python scripts/snapshot.py` every 15 min (Task Scheduler) | `data/raw/snapshots.csv` |
| Campus text | `python scripts/make_building_docs.py` | `graphrag/input/*.txt` |
| Station text | `python scripts/make_station_profiles.py` | `graphrag/input/station_*.txt` |
| Index | `graphrag index --root graphrag` | `graphrag/output/` |
| One query | `python app/graph_query.py local "your question"` | answer and timing |
| App | `streamlit run app/streamlit_app.py` | demo at http://localhost:8501 |

`graphrag/settings.yaml` is set up for Ollama on a CPU laptop: `qwen3:4b` with thinking mode
off, `bge-m3` embeddings, two requests at a time. See `data/README.md` for the data files.

## Layout

```
app/        Streamlit app, hybrid logic, GraphRAG query wrapper
data/       campus places, units, YouBike markers and stations
graphrag/   settings, prompts, input texts (output/ and cache/ are not committed)
scripts/    data preparation
notes/      run log and query timings
```
