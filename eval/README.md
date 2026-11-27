# Evaluation

`questions.csv` is the test set for comparing the retrieval modes (Basic, Local, Global, DRIFT,
Hybrid, Hybrid v2) and for the ablation. Every reference answer comes from a file in `graphrag/input`
(the route questions also from `data/walkway_nodes.csv`).

| Column | Meaning |
| --- | --- |
| `id` | F = fact, M = multi-hop, G = global, S = station, U = unanswerable, L = multilingual |
| `type` | the same groups, spelled out |
| `lang` | `en`, `vi` or `zh` |
| `question` | asked exactly as written |
| `reference_answer` | the correct answer, written from the source files |
| `key_facts` | short strings for automatic checking: `;` separates facts that must all appear, `\|` separates accepted alternatives. `NOT_IN_DATA` means the correct behaviour is to say the data does not contain the answer |
| `source_files` | the input files that hold the answer (`station files` = the station profiles) |
| `station_sno` | the station the question is about, if any |

Question groups and why they are there:

- **fact** (12): one file answers it; basic RAG should already do well.
- **multihop** (12): the answer joins two or more facts, often from different files
  (department → building → what is in front of it). This is where a graph should help.
- **global** (6): a summary across the corpus; Global search and DRIFT are designed for these.
- **station** (6): facts from the station profiles (nearest station, docks, usual busy hours).
- **unanswerable** (4): not in the data; the right answer is to say so (faithfulness).
- **multilingual** (4): Vietnamese and Chinese versions, to test place recognition and retrieval.
- **suitability** (8, R01–R08): "which station should I use, and why", often at a given time; the
  answer needs the gate to use, a station's usual shortage hours or a backup station. Added for
  Hybrid v2.
- **route** (5, W01–W05): "how do I get from A to B" in English, Vietnamese and Chinese. The
  reference follows the walkway graph of the 360° tour; the key facts only ask for what any correct
  answer must say (for example that TR is on Lane 155). Added with the walking routes, so they
  show that the feature works rather than measure it.

Check of the set itself: every reference answer passes its own key facts (57/57).

## Running

From the project folder, with the venv active and Ollama running. Each command writes
`eval/results/<tag>.jsonl` and can be stopped (Ctrl+C) and started again: it continues where it
stopped and retries answers that ended in an error.

All the steps below in one command (192 answers; on a CPU laptop this runs for many hours):

```
python eval/run_eval.py --plan full
```

The same steps one by one:

```
# 1. main comparison, all 44 questions
python eval/run_eval.py --tag main --modes basic,local,hybrid
# 2. modes built for summaries, on the multi-hop and global questions
python eval/run_eval.py --tag main --modes global --types multihop,global
python eval/run_eval.py --tag main --modes drift --types global
# 3. ablation, same index, one setting changed at a time
python eval/run_eval.py --tag noreports --variant noreports --modes local --types multihop,station
python eval/run_eval.py --tag 8b --variant 8b --modes local --types multihop,station
# 4. Hybrid v2: the 18 questions with a recognised place, then the 8 suitability questions in 4 modes
python eval/run_eval.py --plan route
# 5. Hybrid v2 ablation on the same 26 questions: without the GraphRAG context, without the facts
python eval/run_eval.py --plan route_ablation
# 6. walking routes: Basic, Local and Hybrid v2 on the 5 route questions
python eval/run_eval.py --plan walk
# 7. scores
python eval/score_eval.py eval/results/main.jsonl eval/results/noreports.jsonl eval/results/8b.jsonl eval/results/route.jsonl eval/results/h2_nograph.jsonl eval/results/h2_nofacts.jsonl eval/results/walk.jsonl
python eval/score_eval.py eval/results/main.jsonl --show M01,U02
```

Hybrid v2 reads `data/raw/snapshots.csv` when it answers, so its facts change as the log grows.
Each Hybrid v2 answer saves the facts it was given (`facts` in the results file), so a result can
be checked later against exactly what the model saw.

Options: `--ids F01,M03` (only these), `--types`, `--dry-run` (list what would run),
`--root` (another GraphRAG folder), `--response-type` (default `Single Paragraph`, shorter than the
app's `Multiple Paragraphs`, to save time on a CPU). The `hybrid` mode skips the live API call in
the evaluation: live counts never reach the model, so they cannot change the answer.

Ablation variants (no re-indexing; the overrides apply to those queries only):

| Variant | Change | Question it answers |
| --- | --- | --- |
| `noreports` | local search without community reports (`community_prop: 0`) | do community summaries help local answers? |
| `8b` | answers written by `qwen3:8b` instead of the 4B model | is the answer model the bottleneck? |
| `h2_nograph` | Hybrid v2 without the GraphRAG relationships and source texts (computed facts only) | does the graph add anything beyond the facts computed by code? |
| `h2_nofacts` | Hybrid v2 without the computed facts (graph relationships and sources only; the candidate stations are still chosen by distance) | can the graph alone explain the choice? |

The graph itself is ablated by the main comparison: `basic` is vector search over text chunks with
no graph, `local` adds entities, relationships and reports, `hybrid` adds the distance step.

## Scores

`score_eval.py` writes `summary.md` (tables), `summary.html` (charts, open in a browser), `summary.csv`
and `per_answer.csv` next to the results. The charts need no extra packages.

| Score | Meaning |
| --- | --- |
| accuracy | answerable: every key fact appears in the answer; unanswerable: the answer says the data does not contain it |
| key-fact recall | share of key facts found (answerable questions) |
| unanswerable correct | share of the 4 unanswerable questions answered with "not in the data" |
| false refusals | answerable questions answered with "not in the data" and no key fact |
| file hit | the search context contains a text chunk from the expected input file (global search reads reports only, so n/a) |
| median / mean s | seconds per answer on this computer |

**Hand labels.** `eval/results/manual_labels.csv` (columns `system,id,manual,note`) marks each answer
right (1), partly right (0.5) or wrong (0) after reading it against the reference answer. When the file
exists, `score_eval.py` reports these labels next to the automatic scores, with the agreement between
the two, and the charts use them. Rules used: an answer is right only if every part of the question is
answered correctly; extra details are fine unless they contradict the answer; a self-contradicting
answer counts as partly right; "not in the data" for an answerable question is wrong.

Matching ignores case, hyphens, thousands separators and NT$ spellings ("NT$ 40", "40 NTD" and
"40元" all match "40"). It is automatic, so read a sample of answers with `--show`, and report any
answer the matcher gets wrong.
