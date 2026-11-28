# Campus data (NTUST)

All campus data comes from the official Taiwan Tech campus layout map (國立臺灣科技大學校園平面配置圖), read on 2026-11-15. Positions are pixel positions on that map image (2576 x 1517 px) until `scripts/georef.py` converts them to latitude and longitude.

| File | Rows | What it holds |
| --- | --- | --- |
| `buildings.csv` | 61 | Every place on the map: 33 numbered places, gates, sports grounds, parking, shuttle stops, security posts, services, neighbours, and one group row for the dormitory area. Columns: `id, map_no, code, name, name_zh, category, doc_group, aliases, map_x, map_y, lat, lng, coord_source, description`. |
| `campus_units.csv` | 79 | Colleges, departments, institutes, offices, centres and rooms from the map legend, each linked to its building (`building_id`). Used for questions such as "near the CSIE department". |
| `map_youbike_markers.csv` | 7 | The YouBike markers drawn on the map (six 2.0, one 1.0). Only the Back Gate station has a known station number so far (500101027, from OpenStreetMap). Fill `sno` for the others from the API. |
| `georef_anchors.csv` | 5 | Points used to turn map pixels into coordinates. One is filled from OpenStreetMap; fill at least three more from Google Maps. |
| `map_points.png` | | The map with every point drawn on it, for checking positions. |
| `walkway_nodes.csv` | 13 | The panoramas of the 360° campus tour (Tour A) as walkway points: position, where to stand, the YouBike station if the panorama is at one, the iStaging link (`tour_url`, `?index=N` for A0N) and the places the panorama stands next to (`shows`, ids from `buildings.csv`). Written by `scripts/make_walkway.py`; rows with `coord_source` "verified" and links typed by hand are kept. |
| `walkway_edges.csv` | 12 | The hotspot links between those panoramas: the walking paths used for routes. |
| `virtual_tours.csv` | | (optional) `station_id,station_name,tour_url`: a different 360° link for a station card. Without it, a station card opens the Tour A panorama taken at the station. |
| `place_photos.csv` | 7 | Photos of buildings taken by the team (Nov 2026): `place_id,file,credit` (see `photos/README.md`). |
| `demo_questions.txt` | 8 | Questions recorded by `scripts/cache_demo.py` for the live demo; the recordings go to `demo_cache/`. |

## Getting coordinates

1. In Google Maps (satellite view), right click each place in `georef_anchors.csv`, click the first line to copy `lat, lng`, and paste the two numbers into the row.
2. Run `python scripts/georef.py`. It prints the error at each anchor; under about 15 m is good for a drawn map.
3. For a place you measure yourself (for example during the field visit), type its `lat` and `lng` and set `coord_source` to `verified`. Re-running georef never overwrites verified rows.

## Text for GraphRAG

`python scripts/make_building_docs.py` writes 23 files into `graphrag/input/` from these CSVs: one per academic or administration building, plus files for the library, auditorium, dining, dormitories, sports grounds, gates and services, and the campus surroundings. Re-run it after editing the CSVs.

Positions in the text are described by the surrounding roads (Keelung Road front, Lane 155 side, Alley 68 back, Lane 41 and Lane 73 side), not by compass directions, because the map is not drawn with north at the top.

## Alias matching

`scripts/nearest_station.py` matches Chinese aliases anywhere in a question and Latin-script aliases (English, Vietnamese, building codes) as whole words only, so `TR` does not match inside "station". When several aliases match, the longest wins. A question with no known place returns `None`, and the app should ask which building the user means.
