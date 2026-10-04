"""Step 1: the food places of Bengaluru, from OpenStreetMap through the Overpass API.

    ~/tools/venv/bin/python download.py   -> data/food_places.json  data/boundary.json, results/pull.json

Two polite Overpass queries (descriptive User-Agent), nothing else:
  1. every node and way tagged amenity = restaurant, cafe, fast_food, bar, pub, food_court or ice_cream inside the area of OSM relation 7902476, "Bengaluru"
     (admin_level 7, operated by the Greater Bengaluru Authority), with tags and, for ways, the centre Overpass computes (`out center`);
  2. the geometry of that same relation (its outer and inner rings), used as the study area, to measure its size and to place random points.
OSM changes every minute, so a rerun returns slightly different data: results/pull.json records the OSM database timestamp of each answer and the checksums.
Overpass usage policy (wiki.openstreetmap.org/wiki/Overpass_API): under 10,000 queries and 1 GB a day is fine for a one-off; each run uses 2 queries.
robots.txt of overpass-api.de disallows /api/ for generic crawlers; the usage policy above is what governs the interpreter, which is meant to be queried.
Licence: data (c) OpenStreetMap contributors, Open Database Licence (ODbL) 1.0, https://www.openstreetmap.org/copyright. Cite: "OpenStreetMap contributors".
Not committed: data/ (the raw JSON). Committed: results/ (aggregates only: counts, shares, distances; no names of places, no coordinates of single places).
"""
import hashlib
import json
import ssl
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import certifi

HERE = Path(__file__).parent
URL = "https://overpass-api.de/api/interpreter"
TYPES = "restaurant|cafe|fast_food|bar|pub|food_court|ice_cream"
QUERIES = {
    "food_places.json": f'[out:json][timeout:300];area(3607902476)->.a;(node["amenity"~"^({TYPES})$"](area.a);way["amenity"~"^({TYPES})$"](area.a););out center tags;',
    "boundary.json": f'[out:json][timeout:300];rel(7902476);out geom;',
}
CTX = ssl.create_default_context(cafile=certifi.where())


def main():
    (HERE / "data").mkdir(exist_ok=True)
    (HERE / "results").mkdir(exist_ok=True)
    info = {"pulled": date.today().isoformat(), "files": {}}
    for name, q in QUERIES.items():
        for attempt in range(5):
            try:
                req = urllib.request.Request(URL, data=urllib.parse.urlencode({"data": q}).encode(), headers={"User-Agent": "research-portfolio (Rishit Raj Mathur)"})
                raw = urllib.request.urlopen(req, context=CTX, timeout=360).read(); break
            except OSError as e:
                if attempt == 4: raise
                print("retry", name, e); time.sleep(30 * (attempt + 1))
        (HERE / "data" / name).write_bytes(raw)
        base = json.loads(raw)["osm3s"]["timestamp_osm_base"]
        info["files"][name] = {"url": URL, "query": q, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "osm_base": base}
        time.sleep(10)
    (HERE / "results" / "pull.json").write_text(json.dumps(info, indent=2) + "\n")
    print(json.dumps({k: (v["bytes"], v["osm_base"]) for k, v in info["files"].items()}))


if __name__ == "__main__":
    main()
