# Campus YouBike Guide (NTUST)

A question answering assistant that helps students choose a YouBike station around the
Taiwan Tech campus. Knowledge comes from GraphRAG over a small campus corpus, running on a
local model through Ollama on a CPU laptop. Live bike counts come straight from the Taipei
YouBike API and never pass through the language model.

Final project for *Data Mining and Knowledge Discovery* (NTUST, 115-1).

**Research question.** On a small, place-centred corpus, does a knowledge graph (GraphRAG)
answer campus mobility questions better than plain vector RAG, and does adding computed
distances and live data (Hybrid) help further, when everything runs on a local 4B model?

## How it works

```
campus map, building and gate texts, YouBike FAQ, station profiles (47 files)
        │  graphrag index (qwen3:4b-instruct + bge-m3 through Ollama)
        ▼
knowledge graph: 348 entities, 453 relationships, 37 communities with reports
        │
question ──► Basic | Local | Global | DRIFT | Hybrid ──► answer with citations
                                                │
             Hybrid: place in the question ─► nearest stations by coordinates
                                            ─► live counts from the YouBike API (shown in cards, not given to the model)
```

- **Basic**: vector search over text chunks, no graph (the traditional RAG baseline).
- **Local**: entities that match the question, their neighbours, linked text chunks and community reports.
- **Global**: map-reduce over community reports, for overview questions.
- **DRIFT**: a Global primer followed by Local follow-up questions.
- **Hybrid** (this project): recognises the campus place in the question, computes the three nearest
  stations from coordinates, adds them to a Local search, and shows live station cards and a map.

## Quick start (Windows 11, PowerShell)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
ollama pull qwen3:4b-instruct-2507-q4_K_M
ollama pull bge-m3
python -m streamlit run app/streamlit_app.py
```

The finished index (`graphrag/output/`) is in the repository, so the app runs without indexing.
To rebuild it: `graphrag index --root graphrag` (about 6 hours on a CPU laptop; see the timings below).

## Pipeline

| Step | Command | Output |
| --- | --- | --- |
| Place coordinates | `python scripts/georef.py` | lat, lng in `data/buildings.csv` |
| Campus stations | `python scripts/fetch_stations.py --radius 300` | `data/stations_campus.csv` |
| Bike count history | `python scripts/snapshot.py` every 15 min (Task Scheduler) | `data/raw/snapshots.csv` |
| Campus text | `python scripts/make_building_docs.py` | `graphrag/input/*.txt` |
| Station text | `python scripts/make_station_profiles.py --date 2026-11-18` | `graphrag/input/station_*.txt` |
| Index | `graphrag index --root graphrag` | `graphrag/output/` |
| Index timings | `python scripts/cache_report.py graphrag --calls` | calls, tokens, minutes per step |
| One query | `python app/graph_query.py local "your question"` | answer and timing |
| Debug one question | `python scripts/debug_retrieval.py graphrag "your question"` | what local search retrieved |
| App | `python -m streamlit run app/streamlit_app.py` | demo at http://localhost:8501 |
| Evaluation | `python eval/run_eval.py --plan full`, then `python eval/score_eval.py ...` | `eval/results/` |

`graphrag/settings.yaml` is set up for Ollama on a CPU laptop: `qwen3:4b-instruct-2507-q4_K_M`
(the plain `qwen3:4b` tag keeps thinking even with `think: false`), `bge-m3` embeddings, one
request at a time, chunks of 400 tokens, at most 3,000 output tokens per call, `seed: 42`,
`use_lcc: false` (keeps small graph components such as fee entities searchable) and a lighter
DRIFT (2 primer folds, depth 1, 3 follow-ups). The entity types and the extraction prompt in
`graphrag/prompts/extract_graph.txt` are adapted to the campus domain (16 entity types).

## The app

- **Ask**: a question box with a retrieval-mode menu (with the measured time of each mode),
  the nearest station with live bikes and free docks, a campus map, backup stations, the
  answer with its citations, "How this answer was found" (the part of the graph the model
  saw) and the sources.
- **Knowledge graph**: the whole graph, coloured by entity type or by community, with a
  focus mode and entity details.
- Each station card links to a 360° iStaging tour when `data/virtual_tours.csv` has one.

## Evaluation

44 questions with reference answers (`eval/questions.csv`): 12 fact, 12 multi-hop, 6 global,
6 station, 4 unanswerable, 4 multilingual (Vietnamese, Chinese). Every one of the 192 answers was
checked by hand (right, partly right, wrong); an automatic key-fact score is reported next to it.
Details: `eval/README.md`; tables and charts: `eval/results/summary.md`, `summary.html`.

| Mode | Answers | Fully right (by hand) | Median seconds |
| --- | ---: | ---: | ---: |
| Basic (vector RAG) | 44 | **80%** | **93** |
| Local (GraphRAG) | 44 | 66% | 237 |
| Hybrid (Local + distances) | 44 | 73% | 244 |
| Global | 18 (multi-hop, global) | 22% | 388 |
| DRIFT | 6 (global) | 0% | 1603 |

Ablation on the same 18 multi-hop and station questions, no re-indexing:

| Change | Fully right | Median seconds |
| --- | ---: | ---: |
| Local, default | 50% | 234 |
| Local without community reports | **67%** | 266 |
| Local with `qwen3:8b` writing the answer | 50% | 340 |

Main findings:

1. On a corpus this small (60 chunks), vector RAG is strong: ten chunks cover a sixth of the corpus.
   Local search sometimes anchors on generic hub entities and misses the right file.
2. Hybrid is best on station questions (83% against 50%): distances come from coordinates, not the model.
3. Hybrid adds the station list to the search query, which sometimes pulls the search towards
   station entities (questions F10, L02). Searching with the original question is the next fix.
4. Community reports hurt Local search here; removing them raised accuracy from 9 to 12 of 18.
5. A larger answer model does not help: the bottleneck is retrieval, not generation.
6. All four unanswerable questions were refused in every mode (no invented answers).

## Local AI deployment

Everything runs on a CPU-only Windows laptop through Ollama. Indexing took 206 model calls and
433,235 tokens (about 5.8 hours of model time). With `seed: 42` the answers are repeatable: when
Hybrid recognises no place it gives exactly the Local answer, word for word.

## Layout

```
app/        Streamlit app (streamlit_app.py, ui.py), hybrid logic, GraphRAG query wrapper, graph views
data/       campus places, units, YouBike markers and stations, virtual tour links
eval/       questions, evaluation runner, scorer, charts, results and hand labels
graphrag/   settings, prompts, input texts, output (the index); cache/ is not committed
scripts/    data preparation and debugging
notes/      run log and query timings
```

## Data sources

Campus places and units from the official NTUST campus map; station data from the Taipei
YouBike 2.0 open data API; FAQ, fee and rule texts summarised from the official YouBike website.
Each input file names its source on its first line. Used for coursework.
