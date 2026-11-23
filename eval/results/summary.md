# Evaluation results

Files: `main.jsonl`, `noreports.jsonl`, `8b.jsonl`, `route.jsonl`

## Overall

| System | Answers | Accuracy | Key-fact recall | Unanswerable correct | False refusals | File hit | Median s | Mean s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| basic | 52 | 83% | 86% | 100% | 6% | 85% | 101 | 99 |
| local | 52 | 63% | 77% | 100% | 6% | 81% | 245 | 256 |
| hybrid | 52 | 75% | 83% | 100% | 6% | 85% | 247 | 263 |
| hybrid2 | 26 | 96% | 98% | 100% | 0% | 100% | 130 | 116 |
| global | 18 | 33% | 58% | – | 6% | – | 388 | 451 |
| drift | 6 | 17% | 42% | – | 0% | 83% | 1603 | 1464 |
| local+8b | 18 | 67% | 81% | – | 0% | 89% | 340 | 341 |
| local+noreports | 18 | 78% | 88% | – | 0% | 89% | 266 | 260 |

## Checked by hand

Each answer read and marked right (1), partly right (0.5) or wrong (0). Agreement = how often the automatic score gives the same right/wrong verdict.

| System | Checked | Fully right | Score with half credit | Automatic accuracy | Agreement |
| --- | ---: | ---: | ---: | ---: | ---: |
| basic | 52 | 71% | 76% | 83% | 88% |
| local | 52 | 58% | 71% | 63% | 87% |
| hybrid | 52 | 67% | 77% | 75% | 85% |
| hybrid2 | 26 | 92% | 96% | 96% | 96% |
| global | 18 | 22% | 50% | 33% | 89% |
| drift | 6 | 0% | 42% | 17% | 83% |
| local+8b | 18 | 50% | 69% | 67% | 83% |
| local+noreports | 18 | 67% | 75% | 78% | 78% |

Fully right by question type (by hand):

| System | fact | multihop | global | station | unanswerable | multilingual | suitability |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| basic | 92% (12) | 75% (12) | 83% (6) | 50% (6) | 100% (4) | 75% (4) | 25% (8) |
| local | 75% (12) | 50% (12) | 50% (6) | 50% (6) | 100% (4) | 100% (4) | 12% (8) |
| hybrid | 75% (12) | 67% (12) | 50% (6) | 83% (6) | 100% (4) | 75% (4) | 38% (8) |
| hybrid2 | 100% (1) | 75% (8) | – | 100% (5) | 100% (2) | 100% (2) | 100% (8) |
| global | – | 25% (12) | 17% (6) | – | – | – | – |
| drift | – | – | 0% (6) | – | – | – | – |
| local+8b | – | 50% (12) | – | 50% (6) | – | – | – |
| local+noreports | – | 75% (12) | – | 50% (6) | – | – | – |

## Accuracy by question type (automatic)

| System | fact | multihop | global | station | unanswerable | multilingual | suitability |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| basic | 100% (12) | 83% (12) | 83% (6) | 83% (6) | 100% (4) | 100% (4) | 38% (8) |
| local | 75% (12) | 58% (12) | 50% (6) | 67% (6) | 100% (4) | 100% (4) | 25% (8) |
| hybrid | 67% (12) | 75% (12) | 50% (6) | 83% (6) | 100% (4) | 75% (4) | 88% (8) |
| hybrid2 | 100% (1) | 88% (8) | – | 100% (5) | 100% (2) | 100% (2) | 100% (8) |
| global | – | 42% (12) | 17% (6) | – | – | – | – |
| drift | – | – | 17% (6) | – | – | – | – |
| local+8b | – | 67% (12) | – | 67% (6) | – | – | – |
| local+noreports | – | 83% (12) | – | 67% (6) | – | – | – |

## Ablation (same questions as the base mode)

| Change | Questions | Accuracy base → variant | Recall base → variant | Median s base → variant | By hand base → variant |
| --- | ---: | :---: | :---: | :---: | :---: |
| local+8b | 18 | 61% → 67% | 77% → 81% | 234 → 340 | 50% → 50% |
| local+noreports | 18 | 61% → 78% | 77% → 88% | 234 → 266 | 50% → 67% |
| hybrid2 | 26 | 81% → 96% | 86% → 98% | 255 → 130 | 62% → 92% |

## Per question

✓ right, ◐ partly, ✗ wrong, – not run (by hand where checked, otherwise by key facts)

| Question | basic | local | hybrid | hybrid2 | global | drift | local+8b | local+noreports |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| F01 | ✗ | ✓ | ✓ | – | – | – | – | – |
| F02 | ✓ | ✓ | ✓ | – | – | – | – | – |
| F03 | ✓ | ✗ | ✗ | – | – | – | – | – |
| F04 | ✓ | ✓ | ✓ | – | – | – | – | – |
| F05 | ✓ | ✓ | ✓ | – | – | – | – | – |
| F06 | ✓ | ✓ | ✓ | – | – | – | – | – |
| F07 | ✓ | ✓ | ✓ | – | – | – | – | – |
| F08 | ✓ | ✗ | ✗ | – | – | – | – | – |
| F09 | ✓ | ✓ | ✓ | – | – | – | – | – |
| F10 | ✓ | ◐ | ✗ | ✓ | – | – | – | – |
| F11 | ✓ | ✓ | ✓ | – | – | – | – | – |
| F12 | ✓ | ✓ | ✓ | – | – | – | – | – |
| M01 | ✗ | ✗ | ◐ | ✓ | ✗ | – | ✗ | ✗ |
| M02 | ✓ | ✓ | ✓ | ✓ | ✓ | – | ✓ | ✓ |
| M03 | ✓ | ✓ | ✓ | ✓ | ✓ | – | ◐ | ✓ |
| M04 | ✓ | ✗ | ✓ | ◐ | ◐ | – | ✓ | ✓ |
| M05 | ✓ | ◐ | ✓ | ✓ | ◐ | – | ◐ | ✓ |
| M06 | ✓ | ✓ | ✓ | ✓ | ✗ | – | ✓ | ✓ |
| M07 | ✓ | ✓ | ✓ | – | ✓ | – | ✓ | ✓ |
| M08 | ✓ | ✓ | ✓ | – | ✗ | – | ◐ | ✓ |
| M09 | ✗ | ◐ | ◐ | – | ✗ | – | ✗ | ✗ |
| M10 | ✓ | ◐ | ◐ | – | ◐ | – | ✓ | ✓ |
| M11 | ✗ | ◐ | ◐ | ◐ | ◐ | – | ◐ | ◐ |
| M12 | ✓ | ✓ | ✓ | ✓ | ◐ | – | ✓ | ✓ |
| G01 | ✓ | ◐ | ◐ | – | ◐ | ✗ | – | – |
| G02 | ◐ | ✓ | ✓ | – | ◐ | ◐ | – | – |
| G03 | ✓ | ✓ | ✓ | – | ◐ | ◐ | – | – |
| G04 | ✓ | ◐ | ◐ | – | ◐ | ◐ | – | – |
| G05 | ✓ | ✓ | ✓ | – | ✓ | ◐ | – | – |
| G06 | ✓ | ◐ | ◐ | – | ◐ | ◐ | – | – |
| S01 | ◐ | ◐ | ✓ | ✓ | – | – | ◐ | ◐ |
| S02 | ✗ | ✗ | ✗ | ✓ | – | – | ◐ | ✗ |
| S03 | ✓ | ◐ | ✓ | ✓ | – | – | ◐ | ◐ |
| S04 | ✓ | ✓ | ✓ | ✓ | – | – | ✓ | ✓ |
| S05 | ✓ | ✓ | ✓ | – | – | – | ✓ | ✓ |
| S06 | ✗ | ✓ | ✓ | ✓ | – | – | ✓ | ✓ |
| U01 | ✓ | ✓ | ✓ | – | – | – | – | – |
| U02 | ✓ | ✓ | ✓ | ✓ | – | – | – | – |
| U03 | ✓ | ✓ | ✓ | ✓ | – | – | – | – |
| U04 | ✓ | ✓ | ✓ | – | – | – | – | – |
| L01 | ✗ | ✓ | ✓ | – | – | – | – | – |
| L02 | ✓ | ✓ | ✗ | ✓ | – | – | – | – |
| L03 | ✓ | ✓ | ✓ | ✓ | – | – | – | – |
| L04 | ✓ | ✓ | ✓ | – | – | – | – | – |
| R01 | ◐ | ◐ | ✓ | ✓ | – | – | – | – |
| R02 | ✓ | ✓ | ✓ | ✓ | – | – | – | – |
| R03 | ✗ | ◐ | ◐ | ✓ | – | – | – | – |
| R04 | ✓ | ✗ | ✓ | ✓ | – | – | – | – |
| R05 | ◐ | ◐ | ◐ | ✓ | – | – | – | – |
| R06 | ◐ | ◐ | ✗ | ✓ | – | – | – | – |
| R07 | ✗ | ✗ | ✗ | ✓ | – | – | – | – |
| R08 | ✗ | ✗ | ◐ | ✓ | – | – | – | – |

Accuracy counts answerable questions with every key fact present and unanswerable questions answered with 'not in the data'. Key facts are matched as text (case, hyphens, thousands separators and NT$ spellings normalised), so check a sample by hand with `--show`.
