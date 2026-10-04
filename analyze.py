"""Steps 2-4: audit the OpenStreetMap food places of Bengaluru, then ask where they are, what they serve, who runs them and how well they are described.

    ~/tools/venv/bin/python analyze.py   -> results/*.csv  (a minute or so)

Study area: OSM relation 7902476 "Bengaluru" (outer ways stitched into closed rings by matching end points). Everything is in metres on an equirectangular
projection centred on the relation's own admin_centre node: x = R cos(lat0) (lon - lon0), y = R (lat - lat0), R = 6371008.8 m. Over a 40 km city it is good to ~0.1%.
Places: every node, and the centre Overpass gives for every way (the centre of the way's bounding box, not its centroid), tagged amenity = restaurant, cafe, fast_food,
bar, pub, food_court or ice_cream. Points are kept only if they fall inside the stitched polygon (even-odd ray casting); the rest are counted and dropped.
Where: places per 1 km grid cell (and the share in the busiest 5% of occupied cells); places per km2 in distance rings 0-2, 2-5, 5-10, 10-15, 15+ km from the centre,
the ring areas measured on a 250 m raster (a scanline over the polygon), checked against the shoelace area.
Clustering: for every place the distance to its nearest neighbour (Clark-Evans R = observed mean / expected) and Ripley's K(r) at 100, 250, 500, 1000 m (ordered pairs
within r, K = A pairs / (n (n-1)), no edge correction), against two baselines of 19 simulated sets each, the same size as the data and inside the same polygon (so the edge
bias cancels): (A) uniform random points; (B) the same number of random points in every 1 km cell as the data has, uniform within the cell (the city is far from uniform, so B
asks about clustering beyond the coarse density). Random points use the standard library's random.Random with a fixed string seed per set so check.py can redraw them.
Cuisine: the tag split on ';', lower-cased, spaces to '_'; a place with several cuisines counts under each. Chains: names lower-cased, punctuation dropped, spaces collapsed;
a chain is a name that occurs at least 5 times. Completeness: name, cuisine, opening_hours, phone (or contact:phone) and website (or contact:website).
Duplicates: same normalised name within 50 m (kept in every count, and reported). Stability: the same headline measures for three definitions of "food place".
Only aggregates are written: no place name outside the chain list, and no coordinates of single places.
"""
import csv
import json
import math
import random
import unicodedata
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).parent
D, R = HERE / "data", HERE / "results"
EARTH = 6371008.8
TYPES = ["restaurant", "fast_food", "cafe", "pub", "ice_cream", "bar", "food_court"]
RINGS = [(0, 2), (2, 5), (5, 10), (10, 15), (15, math.inf)]
RADII = (100, 250, 500, 1000)
SIMS, CELL, RASTER, CHAIN_N, DUP_M = 19, 1000.0, 250.0, 5, 50.0
DEFS = {"restaurant only": ["restaurant"], "restaurant, fast food, cafe": ["restaurant", "fast_food", "cafe"], "all seven types": TYPES}
FLAGS = ["name", "cuisine", "opening_hours", "phone", "website"]


def norm_name(s):
    """lower-case, keep letters, numbers and combining marks, everything else (punctuation, symbols) dropped, white space collapsed"""
    keep = "".join(c if unicodedata.category(c)[0] in "LNM" else (" " if c.isspace() else "") for c in s.lower())
    return " ".join(keep.split())


def cuisines(tag):
    return [c for c in (v.strip().lower().replace(" ", "_") for v in tag.split(";")) if c]


def write(name, rows):
    with open(R / name, "w", newline="") as f:
        w = csv.writer(f); w.writerows(rows)


def stitch(ways):
    left, rings = [[(p["lat"], p["lon"]) for p in w["geometry"]] for w in ways], []
    while left:
        ring = left.pop(0)
        while ring[0] != ring[-1]:
            for i, w in enumerate(left):
                if w[0] == ring[-1]: ring += w[1:]
                elif w[-1] == ring[-1]: ring += w[::-1][1:]
                else: continue
                left.pop(i); break
            else:
                raise AssertionError("ring does not close")
        rings.append(ring)
    return rings


def load():
    b = json.load(open(D / "boundary.json"))["elements"][0]
    assert all(m["role"] == "outer" for m in b["members"] if m["type"] == "way")
    centre = next(m for m in b["members"] if m["role"] == "admin_centre")
    lat0, lon0 = math.radians(centre["lat"]), math.radians(centre["lon"])
    proj = lambda lat, lon: (EARTH * math.cos(lat0) * (math.radians(lon) - lon0), EARTH * (math.radians(lat) - lat0))
    rings = [[proj(la, lo) for la, lo in r] for r in stitch([m for m in b["members"] if m["type"] == "way"])]
    els = json.load(open(D / "food_places.json"))["elements"]
    return centre, rings, els, proj


def edges(rings):
    e = [(r[i][0], r[i][1], r[i + 1][0], r[i + 1][1]) for r in rings for i in range(len(r) - 1)]
    return np.array(e).T


EDG = None


def inside(px, py):
    """even-odd ray casting of many points against all polygon edges at once"""
    x1, y1, x2, y2 = EDG; out = np.zeros(len(px), bool)
    for s in range(0, len(px), 400):
        X, Y = px[s:s + 400, None], py[s:s + 400, None]
        cond = (y1 <= Y) != (y2 <= Y)
        with np.errstate(divide="ignore", invalid="ignore"):
            xi = x1 + (Y - y1) * (x2 - x1) / (y2 - y1)
        out[s:s + 400] = ((cond & (X < xi)).sum(axis=1) % 2) == 1
    return out


def draw(rng, need, x0, x1, y0, y1):
    """the first `need` uniform points inside the polygon from a stream of uniform draws in the box (identical to drawing them one at a time)"""
    got = []
    while len(got) < need:
        m = max(200, 2 * (need - len(got)))
        pts = [(x0 + (x1 - x0) * rng.random(), y0 + (y1 - y0) * rng.random()) for _ in range(m)]
        a = np.array(pts); ok = inside(a[:, 0], a[:, 1])
        got += [tuple(p) for p in a[ok]]
    return got[:need]


def nn_and_pairs(pts):
    a = np.array(pts); t = cKDTree(a); d = t.query(a, k=2)[0][:, 1]
    pairs = [int(t.count_neighbors(t, r)) - len(a) for r in RADII]
    return d, pairs


def sim_set(tag, n, box):
    return [draw(random.Random(f"{tag}-{s}"), n, *box) for s in range(SIMS)]


def sim_cells(counts, s):
    pts = []
    for (cx, cy) in sorted(counts):
        rng = random.Random(f"B-{s}-{cx}-{cy}"); need, got = counts[(cx, cy)], []
        while len(got) < need:
            a = np.array([(cx * CELL + CELL * rng.random(), cy * CELL + CELL * rng.random()) for _ in range(max(50, 4 * (need - len(got))))])
            got += [tuple(p) for p in a[inside(a[:, 0], a[:, 1])]]
        pts += got[:need]
    return pts


def raster(rings, box):
    """250 m cells whose centre is inside the polygon, by a scanline per row: [(x, y)] of the cell centres"""
    x0, x1, y0, y1 = box; cells = []
    for j in range(int((y1 - y0) / RASTER) + 1):
        yc = y0 + (j + 0.5) * RASTER; xs = []
        for r in rings:
            for i in range(len(r) - 1):
                (ax, ay), (bx, by) = r[i], r[i + 1]
                if (ay <= yc) != (by <= yc): xs.append(ax + (yc - ay) * (bx - ax) / (by - ay))
        xs.sort()
        for a, b in zip(xs[0::2], xs[1::2]):
            i0, i1 = math.ceil((a - x0) / RASTER - 0.5), math.ceil((b - x0) / RASTER - 0.5)
            cells += [(x0 + (i + 0.5) * RASTER, yc) for i in range(i0, i1)]
    return cells


def main():
    global EDG
    R.mkdir(exist_ok=True)
    centre, rings, els, proj = load(); EDG = edges(rings)
    allx = [p[0] for r in rings for p in r]; ally = [p[1] for r in rings for p in r]; box = (min(allx), max(allx), min(ally), max(ally))
    shoelace = sum(abs(sum(r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1] for i in range(len(r) - 1)) / 2) for r in rings) / 1e6
    ras = raster(rings, box); ras_area = len(ras) * RASTER ** 2 / 1e6
    assert abs(ras_area / shoelace - 1) < 0.01, (ras_area, shoelace)

    P = []
    for e in els:
        lat, lon = (e["lat"], e["lon"]) if e["type"] == "node" else (e["center"]["lat"], e["center"]["lon"])
        t = e["tags"]; x, y = proj(lat, lon)
        P.append({"kind": e["type"], "type": t["amenity"], "x": x, "y": y, "name": t.get("name", ""), "nname": norm_name(t.get("name", "")), "cuis": cuisines(t.get("cuisine", "")),
                  "comma": "," in t.get("cuisine", ""), "brand": "brand" in t or "brand:wikidata" in t,
                  "name_f": bool(norm_name(t.get("name", ""))), "cuisine_f": "cuisine" in t, "opening_hours_f": "opening_hours" in t,
                  "phone_f": "phone" in t or "contact:phone" in t, "website_f": "website" in t or "contact:website" in t})
    ok = inside(np.array([p["x"] for p in P]), np.array([p["y"] for p in P]))
    dropped = int((~ok).sum()); P = [p for p, o in zip(P, ok) if o]; n = len(P)
    for p in P: p["d"] = math.hypot(p["x"], p["y"]); p["cell"] = (math.floor(p["x"] / CELL), math.floor(p["y"] / CELL))
    pts = [(p["x"], p["y"]) for p in P]

    # duplicates: the same normalised name within 50 m
    a = np.array(pts); tree = cKDTree(a); dup = [(i, j) for i, j in tree.query_pairs(DUP_M) if P[i]["nname"] and P[i]["nname"] == P[j]["nname"]]
    in_dup = {k for pr in dup for k in pr}
    nd, _ = nn_and_pairs(pts)
    named = [p for p in P if p["name_f"]]
    audit = [["check", "value"], ["elements returned by Overpass", len(els)], ["nodes", sum(e["type"] == "node" for e in els)], ["ways", sum(e["type"] == "way" for e in els)],
             ["dropped: centre outside the boundary polygon", dropped], ["places analysed", n], ["boundary rings", len(rings)], ["boundary vertices", sum(len(r) - 1 for r in rings)],
             ["area, km2 (shoelace)", shoelace], ["area, km2 (250 m raster)", ras_area], ["centre latitude", centre["lat"]], ["centre longitude", centre["lon"]]]
    audit += [[f"places tagged {t}", sum(p["type"] == t for p in P)] for t in TYPES]
    audit += [["without a name", n - len(named)], ["cuisine values with a comma (wrong separator)", sum(p["comma"] for p in P)], ["pairs with the same name within 50 m", len(dup)],
              ["of which a node and a way", sum(P[i]["kind"] != P[j]["kind"] for i, j in dup)], ["places in such a pair", len(in_dup)], ["places on the same spot as another (distance 0)", int((nd == 0).sum())],
              ["places with a brand or brand:wikidata tag", sum(p["brand"] for p in P)]]
    write("audit.csv", audit)

    # tag completeness by type
    rows = [["amenity", "places"] + FLAGS + ["all_five"]]
    for t in TYPES + ["all"]:
        S = [p for p in P if t == "all" or p["type"] == t]
        rows.append([t, len(S)] + [sum(p[f + "_f"] for p in S) for f in FLAGS] + [sum(all(p[f + "_f"] for f in FLAGS) for p in S)])
    write("types.csv", rows)

    # density: 1 km cells, rings
    cells = Counter(p["cell"] for p in P); srt = sorted(cells.values(), reverse=True); top = math.ceil(0.05 * len(srt))
    write("cells.csv", [["cx", "cy", "places"]] + [[cx, cy, c] for (cx, cy), c in sorted(cells.items())])
    ring_of = lambda d: next(i for i, (lo, hi) in enumerate(RINGS) if lo * 1000 <= d < hi * 1000)
    area_r = Counter(ring_of(math.hypot(x, y)) for x, y in ras)
    chain_names = {k for k, v in Counter(p["nname"] for p in named).items() if v >= CHAIN_N}
    rows = [["ring_km", "area_km2", "places", "named", "chain_places"] + FLAGS]
    for i, (lo, hi) in enumerate(RINGS):
        S = [p for p in P if ring_of(p["d"]) == i]
        rows.append([f"{lo}-{hi}" if hi < math.inf else f"{lo}+", area_r[i] * RASTER ** 2 / 1e6, len(S), sum(p["name_f"] for p in S), sum(p["nname"] in chain_names for p in S)] + [sum(p[f + "_f"] for p in S) for f in FLAGS])
    write("rings.csv", rows)
    dp = sorted(p["d"] for p in P); da = sorted(math.hypot(x, y) for x, y in ras)
    med = lambda v: (v[len(v) // 2] + v[(len(v) - 1) // 2]) / 2
    within5 = sum(p["d"] < 5000 for p in P)
    area5 = sum(1 for x, y in ras if math.hypot(x, y) < 5000) * RASTER ** 2 / 1e6
    write("summary.csv", [["key", "value"], ["occupied 1 km cells", len(srt)], ["cells in the busiest 5%", top], ["places in the busiest 5% of cells", sum(srt[:top])], ["places in the busiest cell", srt[0]],
                          ["places in the busiest 10 cells", sum(srt[:10])], ["median distance of a place from the centre, m", med(dp)], ["median distance of the area from the centre, m", med(da)],
                          ["places within 5 km of the centre", within5], ["area within 5 km of the centre, km2", area5]])

    # clustering: observed against the two simulated baselines
    A = shoelace * 1e6; d, pairs = nn_and_pairs(pts)
    exp_nn = 0.5 * math.sqrt(A / n); se = 0.26136 * math.sqrt(A) / n
    simA = sim_set("A-all", n, box); counts = Counter(p["cell"] for p in P); simB = [sim_cells(counts, s) for s in range(SIMS)]
    def sims(sets):
        out = [nn_and_pairs(s) for s in sets]; m = [float(o[0].mean()) for o in out]
        return m, [float(np.median(o[0])) for o in out], [[o[1][k] for o in out] for k in range(len(RADII))]
    mA, medA, prA = sims(simA); mB, medB, prB = sims(simB)
    cl = [["key", "value"], ["places", n], ["mean nearest-neighbour distance, m", float(d.mean())], ["median nearest-neighbour distance, m", float(np.median(d))],
          ["expected mean distance for uniform random points, m", exp_nn], ["Clark-Evans R, analytic", float(d.mean()) / exp_nn], ["Clark-Evans z", (float(d.mean()) - exp_nn) / se]]
    for tag, m, md in (("A uniform", mA, medA), ("B same count per 1 km cell", mB, medB)):
        cl += [[f"{tag}: mean of the simulated mean distances, m", sum(m) / SIMS], [f"{tag}: smallest simulated mean, m", min(m)], [f"{tag}: largest simulated mean, m", max(m)],
               [f"{tag}: Clark-Evans R against the simulations", float(d.mean()) / (sum(m) / SIMS)], [f"{tag}: mean of the simulated median distances, m", sum(md) / SIMS],
               [f"{tag}: simulated sets with a mean distance at or below the data's", sum(v <= float(d.mean()) for v in m)]]
    write("clustering.csv", cl)
    rows = [["radius_m", "pairs", "K_km2", "L_m", "K_sim_A", "K_sim_B", "K_over_A", "K_over_B", "K_over_A_min", "K_over_B_min"]]
    for k, r in enumerate(RADII):
        K = lambda pr_: A * pr_ / (n * (n - 1)) / 1e6
        ka, kb = [K(v) for v in prA[k]], [K(v) for v in prB[k]]
        rows.append([r, pairs[k], K(pairs[k]), math.sqrt(K(pairs[k]) * 1e6 / math.pi), sum(ka) / SIMS, sum(kb) / SIMS, K(pairs[k]) / (sum(ka) / SIMS), K(pairs[k]) / (sum(kb) / SIMS),
                     K(pairs[k]) / max(ka), K(pairs[k]) / max(kb)])
    write("kfunction.csv", rows)

    # cuisine
    cc = Counter(c for p in P for c in p["cuis"]); tagged = sum(bool(p["cuis"]) for p in P)
    write("cuisine.csv", [["cuisine", "places", "share_of_tagged"]] + [[c, v, v / tagged] for c, v in sorted(cc.items(), key=lambda kv: (-kv[1], kv[0]))[:30]])
    with open(R / "summary.csv", "a", newline="") as f:
        csv.writer(f).writerows([["places with a cuisine tag", tagged], ["distinct cuisine values", len(cc)], ["cuisine values used by one place only", sum(v == 1 for v in cc.values())],
                                 ["cuisine tags in all (a place may have several)", sum(cc.values())]])

    # chains
    nc = Counter(p["nname"] for p in named); rows = [["min_places", "names", "places", "share_of_named", "share_of_all", "with_brand_tag"]]
    for m in (3, 5, 10, 20):
        ch = {k for k, v in nc.items() if v >= m}; pl = [p for p in named if p["nname"] in ch]
        rows.append([m, len(ch), len(pl), len(pl) / len(named), len(pl) / n, sum(p["brand"] for p in pl)])
    write("chains.csv", rows)
    brand_name = Counter(p["nname"] for p in named if p["brand"])
    top20 = sorted(((k, v) for k, v in nc.items() if v >= CHAIN_N), key=lambda kv: (-kv[1], kv[0]))[:20]
    write("chain_names.csv", [["name", "places", "with_brand_tag"]] + [[k, v, brand_name[k]] for k, v in top20])
    ch5 = [p for p in named if p["nname"] in chain_names]
    with open(R / "summary.csv", "a", newline="") as f:
        csv.writer(f).writerows([["chain places with a brand tag", sum(p["brand"] for p in ch5)], ["brand-tagged places outside the chains", sum(p["brand"] for p in named if p["nname"] not in chain_names)],
                                 ["names with a brand tag on at least half of their places, among chains", sum(brand_name[k] * 2 >= nc[k] for k in chain_names)]])

    # stability across the definition of a food place
    rows = [["definition", "places", "within_5km", "chain_places", "named", "cuisine_tagged", "mean_nn_m", "R_analytic", "R_vs_simulated"]]
    for lab, ts in DEFS.items():
        S = [p for p in P if p["type"] in ts]; sp = [(p["x"], p["y"]) for p in S]; dS = nn_and_pairs(sp)[0]; ns = len(S)
        nm = Counter(p["nname"] for p in S if p["name_f"]); chs = {k for k, v in nm.items() if v >= CHAIN_N}
        ms = [float(nn_and_pairs(s)[0].mean()) for s in sim_set("A-all" if ts is TYPES else "A-" + lab, ns, box)]
        rows.append([lab, ns, sum(p["d"] < 5000 for p in S), sum(p["nname"] in chs for p in S if p["name_f"]), sum(p["name_f"] for p in S), sum(bool(p["cuis"]) for p in S), float(dS.mean()),
                     float(dS.mean()) / (0.5 * math.sqrt(A / ns)), float(dS.mean()) / (sum(ms) / SIMS)])
    write("stability.csv", rows)
    print("analyze.py done:", n, "places,", dropped, "dropped,", len(rings), "rings,", round(shoelace, 1), "km2")


if __name__ == "__main__":
    main()
