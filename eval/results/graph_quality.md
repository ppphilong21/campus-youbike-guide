# Knowledge graph quality

Index: `graphrag/output`. 348 entities, 453 relationships, 16 entity types in the schema (`settings.yaml`).

| Check | Count | Share |
| --- | ---: | ---: |
| Entities with a type outside the schema | 24 | 7% |
| Groups of duplicate entities (same title once spacing and punctuation are ignored) | 16 | 32 entities |
| Entities with no relationship | 82 | 24% |
| Relationships from an entity to itself | 0 | 0% |

## Entities per type

| Type | In schema | Entities |
| --- | --- | ---: |
| facility | yes | 51 |
| building | yes | 50 |
| service | yes | 35 |
| road | yes | 30 |
| department | yes | 24 |
| rule | yes | 24 |
| office | yes | 19 |
| youbike_station | yes | 17 |
| landmark | yes | 13 |
| fee | yes | 12 |
| payment_method | yes | 11 |
| district | yes | 10 |
| yobike_station | **no** | 10 |
| user_group | yes | 8 |
| parking | yes | 8 |
| gate | yes | 7 |
| bus_stop | yes | 5 |
| dormitory | **no** | 4 |
| fees | **no** | 3 |
| security_post | **no** | 3 |
| program | **no** | 2 |
| bicycle | **no** | 1 |
| limit | **no** | 1 |

## Types outside the schema

| Type | Entities |
| --- | --- |
| bicycle | YOUBIKE 2 |
| dormitory | 1ST FACULTY DORMITORY, 1ST STUDENT DORMITORY, 2ND FACULTY DORMITORY, 3RD STUDENT DORMITORY |
| fees | NT_10_SUBSIDY, YOUBIKE 2.0, YOUBIKE 2.0E |
| limit | FIVE IC CARDS PER ACCOUNT |
| program | BACHELOR'S PROGRAM OF APPLIED SCIENCE AND TECHNOLOGY, INTER-DISCIPLINARY BACHELOR'S PROGRAM |
| security_post | SECURITY POST (LANE 155 PARKING LOT), SECURITY POST (LANE 41 SIDE), SECURITY POST (MAIN GATE) |
| yobike_station | IB_CORNER_STATION, NTUST BACK GATE, YOUBIKE 1.0 STATION, YOUBIKE 2.0 STATION, YOUBIKE STATION, YOUBIKE2.0_AT_TR_BUILDING, YOUBIKE2.0_GONGGUAN PARK, YOUBIKE2.0_NTU CANCER CENTER, YOUBIKE2.0_NTUST_MAIN_GATE, YOUBIKE2.0_NTUST_SIDE_GATE |

## Duplicate entities

| Same entity written as |
| --- |
| MAIN GATE · MAIN_GATE |
| LANE 155 · LANE_155 |
| ALLEY 68 · ALLEY_68 |
| ATHLETIC FIELD · ATHLETIC_FIELD |
| LANE 41 · LANE_41 |
| IC CARD · IC_CARD |
| YOUBIKE 2.0 · YOUBIKE_2_0 |
| YOUBIKE 2.0E · YOUBIKE_2_0E |
| "SINGLE RENTAL" · SINGLE RENTAL |
| PUBLIC BICYCLE INJURY INSURANCE · PUBLIC_BICYCLE_INJURY_INSURANCE |
| "PULL THE BIKE BACKWARDS" · PULL THE BIKE BACKWARDS |
| "WHEEL ALIGNMENT GROOVE" · WHEEL ALIGNMENT GROOVE |
| TAIPEI CITY SENIOR CARD · TAIPEI_CITY_SENIOR_CARD |
| TAIPEI CITY CHARITY CARD · TAIPEI_CITY_CHARITY_CARD |
| NT$10 SUBSIDY · NT_10_SUBSIDY |
| DISPATCH FEE · DISPATCH_FEE |

Duplicates are only the exact cases above; near-duplicates with different words (for example YOUBIKE2.0_NTUST_MAIN_GATE and NTUST(MAIN GATE) STATION) need a person to judge.
