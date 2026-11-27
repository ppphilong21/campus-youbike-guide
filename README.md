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
- **Hybrid v2, graph route** (this project, `app/graph_route.py`): starts from the places named in the
  question and follows paths place → gate → station on two graphs. A campus layer built by code
  gives exact facts (distances, nearest gates, where each station is marked, and what the bike-count
  snapshots show at the time asked, with the number of snapshots behind it; an hour that was never
  sampled is reported as unknown). The GraphRAG graph gives the
  relationships on paths of up to three steps between the place, the gates and the candidate
  stations, filtered by entity type from the schema, with hub entities skipped, plus the source
  text behind them. The model must cite facts, relationships and sources, and explains why a
  station suits the question, not only which one is nearest.
- **Walking routes** (`app/walk_route.py`): the 13 panoramas of the 360° campus tour are the nodes of
  a walkway graph and its hotspot links are the edges (`data/walkway_nodes.csv`, `walkway_edges.csv`,
  built by `scripts/make_walkway.py`). For "how do I get from IB to TR?", Hybrid v2 joins both places
  to their nearest panoramas, finds the shortest path (Dijkstra) and gives it to the model as a fact
  to put into words. The app draws the route on the map and links each step to its 360° view.
  Questions without route words are not affected.
- **Your location**: when the page opens, the browser asks whether to share the location (it works
  on localhost or https). Once allowed, Hybrid v2 starts from it when the question names no place or
  says "here". The location button sits next to the mode menu and shows the nearest campus place
  ("Around …" when the browser reports an error wider than 60 m). Its menu lets the user type the
  building they are in when the position is off, ask the device again, or stop using the location.

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
| Bike count history | `scripts/snapshot.py` every 15 min, day and night, on GitHub Actions (`.github/workflows/snapshot.yml`); before 23 Nov on the laptop, only while it was awake | `data/raw/snapshots.csv` on the `snapshots` branch |
| Campus text | `python scripts/make_building_docs.py` | `graphrag/input/*.txt` |
| Station text | `python scripts/make_station_profiles.py --date 2026-11-18` | `graphrag/input/station_*.txt` |
| Index | `graphrag index --root graphrag` | `graphrag/output/` |
| Index timings | `python scripts/cache_report.py graphrag --calls` | calls, tokens, minutes per step |
| One query | `python app/graph_query.py local "your question"` | answer and timing |
| Debug one question | `python scripts/debug_retrieval.py graphrag "your question"` | what local search retrieved |
| App | `python -m streamlit run app/streamlit_app.py` | demo at http://localhost:8501 |
| Evaluation | `python eval/run_eval.py --plan full`, then `python eval/score_eval.py ...` | `eval/results/` |
| Hybrid v2 evaluation | `python eval/run_eval.py --plan route` | `eval/results/route.jsonl` |
| Hybrid v2 ablation | `python eval/run_eval.py --plan route_ablation` | `eval/results/h2_nograph.jsonl`, `h2_nofacts.jsonl` |
| Walking route evaluation | `python eval/run_eval.py --plan walk` | `eval/results/walk.jsonl` |
| Walkway graph | `python scripts/make_walkway.py` | `data/walkway_nodes.csv`, `walkway_edges.csv` |
| Graph quality | `python scripts/graph_quality.py` | `eval/results/graph_quality.md` |
| Recorded demo answers | `python scripts/cache_demo.py` | `data/demo_cache/*.json` |

`graphrag/settings.yaml` is set up for Ollama on a CPU laptop: `qwen3:4b-instruct-2507-q4_K_M`
(the plain `qwen3:4b` tag keeps thinking even with `think: false`), `bge-m3` embeddings, one
request at a time, chunks of 400 tokens, at most 3,000 output tokens per call, `seed: 42`,
`use_lcc: false` (keeps small graph components such as fee entities searchable) and a lighter
DRIFT (2 primer folds, depth 1, 3 follow-ups). The entity types and the extraction prompt in
`graphrag/prompts/extract_graph.txt` are adapted to the campus domain (16 entity types).

## The app

- **Ask**: a question box with a retrieval-mode menu (with the measured time of each mode; Hybrid v2,
  shown as **Hybrid** in the menu, is the default and replaces the first Hybrid, which is kept only
  for the evaluation) and the user's location next to it; the place asked about (a photo when `data/place_photos.csv` has one, the
  nearest 360° view); the walking route; the nearest station with live
  bikes and free docks, a campus map, backup stations, the answer with its citations, "How this
  answer was found" (the part of the graph the model saw) and the sources.
- **Knowledge graph**: the whole graph, coloured by entity type or by community, with a
  focus mode and entity details.
- Each station card links to a 360° iStaging tour when `data/virtual_tours.csv` has one
  (columns `station_id,station_name,tour_url`); each walkway step links to its panorama when
  `data/walkway_nodes.csv` has a `tour_url`.
- **Recorded answers for a live demo**: open the app as http://localhost:8501/?recorded=1 and the
  questions recorded beforehand with `scripts/cache_demo.py` are answered at once, labelled
  "Recorded answer", with live station counts (an answer takes 1.5 to 4 minutes on the CPU laptop).
  Other questions are answered by the model as usual.

## Evaluation

44 questions with reference answers (`eval/questions.csv`): 12 fact, 12 multi-hop, 6 global,
6 station, 4 unanswerable, 4 multilingual (Vietnamese, Chinese). Eight suitability questions
(R01–R08: "which station should I use, and why", often at a given time) were added for Hybrid v2;
their answers need the gate, the station's shortage hours or a backup station. Every one of the 242 answers was
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

Hybrid v2 (graph route) on the 18 questions where a campus place is recognised, plus the 8
suitability questions answered by all four modes:

| Mode | 18 place questions | 8 suitability questions | All 26 | Median seconds (26) |
| --- | ---: | ---: | ---: | ---: |
| Basic | 72% | 25% | 58% | 109 |
| Local | 56% | 12% | 42% | 261 |
| Hybrid | 72% | 38% | 62% | 255 |
| **Hybrid v2** | **89%** | **100%** | **92%** | **130** |

Hybrid v2 prompts are about 4,000 tokens (median, instructions included), while Local search fills a
data context of up to 7,000 tokens (`max_context_tokens`), which is probably the main reason it is
faster. Its snapshot facts used the log up to 23 November (5 weekdays); every answer stores the
facts it was given (`facts` in `eval/results/route.jsonl`).

### How the answers were scored

- Each question has a reference answer written from the input files, its key facts (all must
  appear; spelling variants accepted) and the files that hold the answer.
- Automatic score: key facts matched in the answer text (case, hyphens, thousands separators and
  NT$ spellings normalised). It agrees with the hand labels on 86–91% of answers, but it is
  lenient with answers that quote many numbers, so the hand labels are the main result.
- Hand labels: right (1), partly right (0.5) or wrong (0), with a note for every answer that is not
  right (`eval/results/manual_labels.csv`).
- Also measured: key-fact recall, false refusals, whether the retrieved context contains the
  expected file, and seconds per answer.

### Faithfulness and groundedness

- **No invented answers to out-of-scope questions**: the 4 unanswerable questions were answered
  "not in the data" in every mode (12 of 12 for Basic, Local and Hybrid).
- **Citations**: 95–100% of answers cite the records they used (`[Data: Sources (…); Entities (…)]`).
  The app turns these into a "Sources used" list and draws the part of the graph the model saw.
- **Retrieval**: the context contained a chunk from the expected file for 90% (Basic), 88% (Local)
  and 85% (Hybrid) of the answerable questions.
- **Live numbers are grounded by design**: bike and dock counts go from the API to the station
  cards and never through the model, so the model cannot misquote them.
- **Where it fails**: a citation does not guarantee a correct claim. DRIFT invented opening hours;
  the 4B model miscalculated fees (NT$80 for a NT$40 ride); acronyms missing from the data (CSIE)
  caused false refusals (8% of answerable questions).

### Is the difference real?

Paired McNemar tests on the same questions (fully right or not):

| Comparison | Questions | Only first right | Only second right | p |
| --- | ---: | ---: | ---: | ---: |
| Basic vs Local | 44 | 10 | 4 | 0.18 |
| Basic vs Hybrid | 44 | 8 | 5 | 0.58 |
| Local vs Hybrid | 44 | 1 | 4 | 0.38 |
| Local vs Local without reports | 18 | 0 | 3 | 0.25 |
| Local vs Local with qwen3:8b | 18 | 2 | 2 | 1.00 |
| Hybrid vs Hybrid v2 | 26 | 1 | 9 | **0.02** |
| Hybrid vs Hybrid v2, place questions only | 18 | 1 | 4 | 0.38 |
| Hybrid vs Hybrid v2, suitability only | 8 | 0 | 5 | 0.06 |
| Basic vs Hybrid v2 | 26 | 1 | 10 | **0.01** |

None of the differences between the GraphRAG modes and Basic on the 44 questions is significant.
Hybrid v2 is the only change with a significant gain (p < 0.05 on 26 questions), and most of it
comes from the suitability questions, which were written together with Hybrid v2 (see the
limitations).

Main findings:

1. On a corpus this small (60 chunks), vector RAG is strong: ten chunks cover a sixth of the corpus.
   Local search sometimes anchors on generic hub entities and misses the right file.
2. Hybrid is best on station questions (83% against 50%): distances come from coordinates, not the model.
3. Hybrid adds the station list to the search query, which sometimes pulls the search towards
   station entities (questions F10, L02). Searching with the original question is the next fix.
4. Community reports hurt Local search here; removing them raised accuracy from 9 to 12 of 18.
5. A larger answer model does not help: the bottleneck is retrieval, not generation.
6. All four unanswerable questions were refused in every mode (no invented answers).
7. Hybrid v2 answers all 8 suitability questions right, against 1 to 3 of 8 for the other modes.
   The others name the nearest station but miss that it is short at the time asked (R06, R07) or
   contradict themselves about it (R03). The route facts (gate, place on the map, snapshot counts
   at that hour) are computed by code, so the model only has to compare them.
8. On the 18 place questions Hybrid v2 is right on 16, including the two that Hybrid's changed
   search query broke (F10, L02). Its two misses: the units of a building reached through the
   graph but whose own file was not in the context (M04), and the model choosing the wrong
   relationship although the right one was in its context (M11).
9. The automatic score cannot tell a recommended station from a mentioned one: on the suitability
   questions it gives Hybrid 88%, the hand labels 38%. For "which one and why" questions, reading
   the answers is necessary.

## Local AI deployment

Everything runs on a CPU-only Windows laptop through Ollama (about 10 tokens per second when
generating). Indexing took 206 model calls and 433,235 tokens (about 5.8 hours of model time).
With `seed: 42` the answers are repeatable: when Hybrid recognises no place it gives exactly the
Local answer, word for word. Choices made for the CPU: the non-thinking instruct model (the
thinking model spent thousands of tokens per call), one request at a time, 400-token chunks so
extraction answers are not cut off, and a lighter DRIFT. Even so, an answer takes 1.5 to 4 minutes,
and DRIFT about 27, which is too slow for live use; see the limitations below.

## Limitations and future work

- **Small test set**: 44 questions, one corpus, differences not significant. A larger question
  set (and a second annotator for the hand labels) would make the comparison firmer.
- **The suitability questions favour Hybrid v2**: R01–R08 were written while Hybrid v2 was being
  built, and their references use the same station files that Hybrid v2's facts come from. The
  other modes had the same files in their index, but the 100% should be read as "the design works
  on the cases it was designed for", not as a general result. New suitability questions written
  by someone else would be a fairer test.
- **Retrieval, not generation, is the weak point**: Local search can anchor on hub entities and
  Hybrid's station list changes the search query. Hybrid v2 avoids both by starting from the
  places in the question and filtering paths by entity type; its remaining retrieval gap is that
  the source text of an entity reached through the graph (M04) is not always added. Next: add the
  file of every place on the chosen path.
- **Data gaps**: common names and acronyms (CSIE, 資工系 variants) should be added to the building
  files as aliases; the corpus has no opening hours or phone numbers.
- **Community reports** add generic text to Local search on a small corpus; a smaller report
  share or none (`local_search.community_prop`) worked better here.
- **Speed on a CPU**: 4 minutes per answer is acceptable for a demo but not for daily use. A GPU,
  a shorter context (fewer than 7,000 tokens) or caching common questions would help.
- **The bike-count history is thin**: up to 22 November the log has 42 weekday snapshots on 4 days,
  only between 14:00-18:00 and 21:00-24:00, because the laptop slept at other times. A "usual
  shortage" such as Main Gate at 21:00-22:00 rests on 4 snapshots from 2 evenings. The station files
  in the index state their sample size; Hybrid v2 reads the log when a question is asked, reports the
  number of snapshots and days, calls an hour with fewer than 3 snapshots on 2 days "too few to say",
  and an hour never sampled "not known". From 23 November the snapshots run on GitHub Actions
  around the clock; get the latest log with `git fetch origin snapshots` and
  `git checkout origin/snapshots -- data/raw/snapshots.csv`. No re-indexing is needed.
- **The 4B model is weak at arithmetic**: fee questions could be answered by code from the fee
  table, the same way live counts are, instead of by the model.
- **The extracted graph is noisy** (`python scripts/graph_quality.py`, `eval/results/graph_quality.md`):
  24 of 348 entities (7%) got a type outside the 16 of the schema (for example `yobike station`,
  `fees`, `program`); 16 entities are written twice (`IC CARD` and `IC_CARD`, `MAIN GATE` and
  `MAIN_GATE`); 82 entities (24%) have no relationship; a few relationships are wrong ("The Main
  Gate is located on Lane 155"). The graph view shows the 7 stray types under the schema type they
  belong to (`TYPE_FIX` in `app/kg_view.py`, display only; the entity details still say what the
  model wrote). Hybrid v2 keeps the raw types, so its results stay comparable, and works around part
  of the noise with aliases and type filters. Fixing it at the source needs a clean-up step (merge
  duplicates, map stray types to the schema) and a new index.
- **Walking routes cover only the photographed paths**: the walkway graph has the 13 panoramas of
  the 360° tour on two routes (Main Gate → Library → Back Gate, Library → Lane 155 → NTU Cancer
  Center station) and Keelung Road in front of the Main Gate. A place far from them gets a
  straight-line last step, which the facts say.
  The panorama positions come from the campus map until the photos are taken. The route questions
  (W01–W05) were written together with the feature, so they show that it works, not how well.
- **Location**: browsers share the position only on localhost or https and after the user allows
  it. A laptop locates by Wi-Fi, which can be 100 m or more off (in one test from the 2nd Student
  Dormitory the browser reported ±183 m and named the T2 Cafeteria, 108 m away); a phone with GPS
  is usually within 5–20 m. Typing the building in the location menu covers the laptop case.
- **Future work**: availability forecasts per hour once the snapshot log covers a few weeks (or the
  TDX history API, which keeps station counts since June 2021); a walkway graph for the whole
  campus; a LINE bot; other campuses with the same pipeline.

## Layout

```
app/        Streamlit app (streamlit_app.py, ui.py, components/geolocation), hybrid logic, graph route
            (graph_route.py), walking routes (walk_route.py), recorded answers (demo_cache.py), graph views
data/       campus places, units, YouBike markers and stations, walkway graph, virtual tour links,
            place photos, recorded demo answers
eval/       questions, evaluation runner, scorer, charts, results and hand labels
graphrag/   settings, prompts, input texts, output (the index); cache/ is not committed
scripts/    data preparation and debugging
notes/      run log and query timings
```

## Data sources

Campus places and units from the official NTUST campus map; station data from the Taipei
YouBike 2.0 open data API; FAQ, fee and rule texts summarised from the official YouBike website.
Each input file names its source on its first line. Used for coursework.
