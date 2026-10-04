"""Step 5: the project's check. Recompute with different code, in plain Python straight from the downloaded Overpass files (json, csv, math, random and loops: no pandas,
numpy, scipy or shapely), and compare with results/:

    ~/tools/venv/bin/python check.py        (a few minutes)

The study polygon is stitched with an end-point dictionary; the points are tested against it by even-odd ray casting over edges bucketed in 1 km bands; the area is the
shoelace sum and the ring areas come from a raster whose scanline crossings are collected edge by edge. The observed nearest-neighbour distances, Ripley pair counts and
duplicate pairs come from one brute-force loop over all n(n-1)/2 pairs. The simulated random sets are redrawn with random.Random and the same string seeds (a different
polygon test, so a point on the boundary would show up as a mismatch) and measured with an exact sweep over points sorted by x, with a brute-force fallback for any point
whose nearest neighbour lies beyond the sweep window. Every table is then compared cell by cell: counts exactly, everything else at a relative tolerance of 1e-9.
The projection constants and the definitions (cuisine and name normalisation, chain threshold 5, radii, 19 simulations) are the project's specification, restated here.
"""
import csv
import json
import math
import random
import unicodedata
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
D, RES = HERE / "data", HERE / "results"
EARTH, CELL, RASTER, BAND = 6371008.8, 1000.0, 250.0, 1000.0
TYPES = ["restaurant", "fast_food", "cafe", "pub", "ice_cream", "bar", "food_court"]
RING_EDGES = [0, 2000, 5000, 10000, 15000, math.inf]
RING_LABELS = ["0-2", "2-5", "5-10", "10-15", "15+"]
RADII, SIMS, CHAIN_N = (100, 250, 500, 1000), 19, 5
DEFS = {"restaurant only": ["restaurant"], "restaurant, fast food, cafe": ["restaurant", "fast_food", "cafe"], "all seven types": TYPES}
FLAGS = ["name", "cuisine", "opening_hours", "phone", "website"]
n_ok = 0


def same(label, got, want, exact=False):
    global n_ok
    n_ok += 1
    if isinstance(want, str):
        assert got == want, f"{label}: recount {got!r} != results {want!r}"; return
    want = float(want)
    if exact: assert got == want, f"{label}: recount {got} != results {want}"
    else: assert abs(got - want) <= 1e-9 * abs(want) + 1e-12, f"{label}: recount {got} != results {want}"


def rows(name):
    return list(csv.reader(open(RES / name)))


def compare_kv(name, got):
    r = rows(name)[1:]; assert [k for k, _ in r] == list(got), f"{name}: keys differ"
    for k, v in r:
        try: float(v)
        except ValueError: continue
        same(f"{name}/{k}", got[k], float(v), exact=isinstance(got[k], int))


def compare_table(name, got, exact_cols=()):
    r = rows(name); head, body = r[0], r[1:]; assert len(body) == len(got), f"{name}: {len(body)} rows against {len(got)}"
    for line, g in zip(body, got):
        for j, (cell, val) in enumerate(zip(line, g)):
            try: float(cell)
            except ValueError: same(f"{name}/{head[j]}", str(val), cell); continue
            same(f"{name}/{head[j]}", val, float(cell), exact=isinstance(val, int))


def norm_name(s):
    out = []
    for c in s.lower():
        if unicodedata.category(c)[0] in "LNM": out.append(c)
        elif c.isspace(): out.append(" ")
    return " ".join("".join(out).split())


def cuisines(tag):
    out = []
    for v in tag.split(";"):
        v = v.strip().lower().replace(" ", "_")
        if v: out.append(v)
    return out


def stitch(ways):
    ends = {}
    for k, w in enumerate(ways):
        for e in (w[0], w[-1]): ends.setdefault(e, []).append(k)
    used, rings = set(), []
    for k in range(len(ways)):
        if k in used: continue
        used.add(k); ring = list(ways[k])
        while ring[0] != ring[-1]:
            nxt = [j for j in ends[ring[-1]] if j not in used]; assert nxt, "ring does not close"
            used.add(nxt[0]); w = ways[nxt[0]]
            ring += (w[1:] if w[0] == ring[-1] else w[::-1][1:])
        rings.append(ring)
    return rings


# ---- the polygon, the places
bnd = json.load(open(D / "boundary.json"))["elements"][0]
centre = [m for m in bnd["members"] if m["role"] == "admin_centre"][0]
lat0, lon0 = math.radians(centre["lat"]), math.radians(centre["lon"])
def proj(lat, lon): return (EARTH * math.cos(lat0) * (math.radians(lon) - lon0), EARTH * (math.radians(lat) - lat0))
rings = [[proj(*p) for p in r] for r in stitch([[(p["lat"], p["lon"]) for p in m["geometry"]] for m in bnd["members"] if m["type"] == "way"])]
EDGES = [(r[i][0], r[i][1], r[i + 1][0], r[i + 1][1]) for r in rings for i in range(len(r) - 1)]
XMIN, XMAX = min(e[0] for e in EDGES), max(e[0] for e in EDGES); YMIN, YMAX = min(e[1] for e in EDGES), max(e[1] for e in EDGES)
nb = int((YMAX - YMIN) / BAND) + 2; BUCKET = [[] for _ in range(nb)]
for e in EDGES:
    for b in range(int((min(e[1], e[3]) - YMIN) / BAND), int((max(e[1], e[3]) - YMIN) / BAND) + 1): BUCKET[b].append(e)


def inside(x, y):
    if not (XMIN <= x <= XMAX and YMIN <= y <= YMAX): return False
    c = 0
    for x1, y1, x2, y2 in BUCKET[int((y - YMIN) / BAND)]:
        if (y1 <= y) != (y2 <= y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1): c += 1
    return c % 2 == 1


AREA = sum(abs(sum(r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1] for i in range(len(r) - 1))) / 2 for r in rings) / 1e6
els = json.load(open(D / "food_places.json"))["elements"]
P, dropped = [], 0
for e in els:
    ll = (e["lat"], e["lon"]) if e["type"] == "node" else (e["center"]["lat"], e["center"]["lon"]); x, y = proj(*ll)
    if not inside(x, y): dropped += 1; continue
    t = e["tags"]; nn = norm_name(t.get("name", ""))
    P.append(dict(kind=e["type"], type=t["amenity"], x=x, y=y, nname=nn, cuis=cuisines(t.get("cuisine", "")), comma="," in t.get("cuisine", ""), brand=("brand" in t or "brand:wikidata" in t),
                  d=math.hypot(x, y), cell=(math.floor(x / CELL), math.floor(y / CELL)),
                  name_f=nn != "", cuisine_f="cuisine" in t, opening_hours_f="opening_hours" in t, phone_f=("phone" in t or "contact:phone" in t), website_f=("website" in t or "contact:website" in t)))
N = len(P)

# ---- raster of the polygon, edge by edge
cross = {}
for ax, ay, bx, by in EDGES:
    lo, hi = min(ay, by), max(ay, by)
    j0, j1 = math.ceil((lo - YMIN) / RASTER - 0.5), math.ceil((hi - YMIN) / RASTER - 0.5)
    for j in range(j0, j1):
        yc = YMIN + (j + 0.5) * RASTER
        if (ay <= yc) != (by <= yc): cross.setdefault(j, []).append(ax + (yc - ay) * (bx - ax) / (by - ay))
RAS = []
for j, xs in cross.items():
    xs.sort(); yc = YMIN + (j + 0.5) * RASTER
    for a, b in zip(xs[0::2], xs[1::2]):
        for i in range(math.ceil((a - XMIN) / RASTER - 0.5), math.ceil((b - XMIN) / RASTER - 0.5)): RAS.append((XMIN + (i + 0.5) * RASTER, yc))


def ring_of(d):
    for i in range(5):
        if RING_EDGES[i] <= d < RING_EDGES[i + 1]: return i


# ---- the brute-force pass over all pairs of the observed places
def brute(pts, names=None):
    n = len(pts); best = [math.inf] * n; cnt = [0] * len(RADII); r2 = [r * r for r in RADII]; dups = []
    for i in range(n):
        xi, yi = pts[i]; bi = best[i]
        for j in range(i + 1, n):
            dx = pts[j][0] - xi; dy = pts[j][1] - yi; d2 = dx * dx + dy * dy
            if d2 < bi: bi = d2
            if d2 < best[j]: best[j] = d2
            if d2 <= 1000000.0:
                if d2 <= r2[3]: cnt[3] += 1
                if d2 <= r2[2]: cnt[2] += 1
                if d2 <= r2[1]: cnt[1] += 1
                if d2 <= r2[0]: cnt[0] += 1
            if names is not None and d2 <= 2500.0 and names[i] and names[i] == names[j]: dups.append((i, j))
        best[i] = bi
    return [math.sqrt(b) for b in best], [2 * c for c in cnt], dups


def sweep(pts):
    """exact nearest-neighbour distances and ordered pair counts within the radii, scanning points sorted by x within a 1 km window"""
    s = sorted(pts); n = len(s); best = [math.inf] * n; cnt = [0] * len(RADII); r2 = [r * r for r in RADII]
    for i in range(n):
        xi, yi = s[i]
        for j in range(i + 1, n):
            dx = s[j][0] - xi
            if dx > 1000.0: break
            dy = s[j][1] - yi; d2 = dx * dx + dy * dy
            if d2 < best[i]: best[i] = d2
            if d2 < best[j]: best[j] = d2
            for k in range(4):
                if d2 <= r2[k]: cnt[k] += 1
    for i in range(n):
        if best[i] > 1000000.0:
            xi, yi = s[i]; best[i] = min((s[j][0] - xi) ** 2 + (s[j][1] - yi) ** 2 for j in range(n) if j != i)
    return [math.sqrt(b) for b in best], [2 * c for c in cnt]


def median(v):
    v = sorted(v); return (v[len(v) // 2] + v[(len(v) - 1) // 2]) / 2


def draw_uniform(tag, s, need):
    rng = random.Random(f"{tag}-{s}"); out = []
    while len(out) < need:
        x = XMIN + (XMAX - XMIN) * rng.random(); y = YMIN + (YMAX - YMIN) * rng.random()
        if inside(x, y): out.append((x, y))
    return out


def draw_cells(counts, s):
    out = []
    for (cx, cy) in sorted(counts):
        rng = random.Random(f"B-{s}-{cx}-{cy}"); got = 0
        while got < counts[(cx, cy)]:
            x = cx * CELL + CELL * rng.random(); y = cy * CELL + CELL * rng.random()
            if inside(x, y): out.append((x, y)); got += 1
    return out


def sim_stats(sets):
    res = [sweep(s) for s in sets]
    return [sum(r[0]) / len(r[0]) for r in res], [median(r[0]) for r in res], [[r[1][k] for r in res] for k in range(len(RADII))]


# ---- the audit
names = [p["nname"] for p in P]; pts = [(p["x"], p["y"]) for p in P]
nnd, pairs, dup = brute(pts, names)
in_dup = set(i for pr in dup for i in pr); named = [p for p in P if p["name_f"]]
audit = {"elements returned by Overpass": len(els), "nodes": sum(e["type"] == "node" for e in els), "ways": sum(e["type"] == "way" for e in els), "dropped: centre outside the boundary polygon": dropped,
         "places analysed": N, "boundary rings": len(rings), "boundary vertices": len(EDGES), "area, km2 (shoelace)": AREA, "area, km2 (250 m raster)": len(RAS) * RASTER ** 2 / 1e6,
         "centre latitude": centre["lat"], "centre longitude": centre["lon"]}
for t in TYPES: audit[f"places tagged {t}"] = sum(p["type"] == t for p in P)
audit.update({"without a name": N - len(named), "cuisine values with a comma (wrong separator)": sum(p["comma"] for p in P), "pairs with the same name within 50 m": len(dup),
              "of which a node and a way": sum(P[i]["kind"] != P[j]["kind"] for i, j in dup), "places in such a pair": len(in_dup), "places on the same spot as another (distance 0)": sum(d == 0 for d in nnd),
              "places with a brand or brand:wikidata tag": sum(p["brand"] for p in P)})
compare_kv("audit.csv", audit)

# ---- tag completeness
tb = []
for t in TYPES + ["all"]:
    S = [p for p in P if t == "all" or p["type"] == t]; tb.append([t, len(S)] + [sum(p[f + "_f"] for p in S) for f in FLAGS] + [sum(all(p[f + "_f"] for f in FLAGS) for p in S)])
compare_table("types.csv", tb)

# ---- density
cells = Counter(p["cell"] for p in P); compare_table("cells.csv", [[cx, cy, c] for (cx, cy), c in sorted(cells.items())])
chain_names = set(k for k, v in Counter(p["nname"] for p in named).items() if v >= CHAIN_N)
area_r = [0] * 5
for x, y in RAS: area_r[ring_of(math.hypot(x, y))] += 1
rb = []
for i in range(5):
    S = [p for p in P if ring_of(p["d"]) == i]
    rb.append([RING_LABELS[i], area_r[i] * RASTER ** 2 / 1e6, len(S), sum(p["name_f"] for p in S), sum(p["nname"] in chain_names for p in S)] + [sum(p[f + "_f"] for p in S) for f in FLAGS])
compare_table("rings.csv", rb)
srt = sorted(cells.values(), reverse=True); top = math.ceil(0.05 * len(srt)); tagged = sum(bool(p["cuis"]) for p in P)
cc = Counter(c for p in P for c in p["cuis"]); nc = Counter(p["nname"] for p in named); ch5 = [p for p in named if p["nname"] in chain_names]
brand_name = Counter(p["nname"] for p in named if p["brand"])
summary = {"occupied 1 km cells": len(srt), "cells in the busiest 5%": top, "places in the busiest 5% of cells": sum(srt[:top]), "places in the busiest cell": srt[0], "places in the busiest 10 cells": sum(srt[:10]),
           "median distance of a place from the centre, m": median([p["d"] for p in P]), "median distance of the area from the centre, m": median([math.hypot(x, y) for x, y in RAS]),
           "places within 5 km of the centre": sum(p["d"] < 5000 for p in P), "area within 5 km of the centre, km2": sum(1 for x, y in RAS if math.hypot(x, y) < 5000) * RASTER ** 2 / 1e6,
           "places with a cuisine tag": tagged, "distinct cuisine values": len(cc), "cuisine values used by one place only": sum(v == 1 for v in cc.values()), "cuisine tags in all (a place may have several)": sum(cc.values()),
           "chain places with a brand tag": sum(p["brand"] for p in ch5), "brand-tagged places outside the chains": sum(p["brand"] for p in named if p["nname"] not in chain_names),
           "names with a brand tag on at least half of their places, among chains": sum(brand_name[k] * 2 >= nc[k] for k in chain_names)}
compare_kv("summary.csv", summary)

# ---- clustering
A = AREA * 1e6; mean_obs = sum(nnd) / N; exp_nn = 0.5 * math.sqrt(A / N); se = 0.26136 * math.sqrt(A) / N
sim_cache = {}
def simA(tag, n):
    if tag not in sim_cache: sim_cache[tag] = sim_stats([draw_uniform(tag, s, n) for s in range(SIMS)])
    return sim_cache[tag]
mA, medA, prA = simA("A-all", N); counts = dict(cells); mB, medB, prB = sim_stats([draw_cells(counts, s) for s in range(SIMS)])
cl = {"places": N, "mean nearest-neighbour distance, m": mean_obs, "median nearest-neighbour distance, m": median(nnd), "expected mean distance for uniform random points, m": exp_nn,
      "Clark-Evans R, analytic": mean_obs / exp_nn, "Clark-Evans z": (mean_obs - exp_nn) / se}
for tag, m, md in (("A uniform", mA, medA), ("B same count per 1 km cell", mB, medB)):
    cl.update({f"{tag}: mean of the simulated mean distances, m": sum(m) / SIMS, f"{tag}: smallest simulated mean, m": min(m), f"{tag}: largest simulated mean, m": max(m),
               f"{tag}: Clark-Evans R against the simulations": mean_obs / (sum(m) / SIMS), f"{tag}: mean of the simulated median distances, m": sum(md) / SIMS,
               f"{tag}: simulated sets with a mean distance at or below the data's": sum(v <= mean_obs for v in m)})
compare_kv("clustering.csv", cl)
kb = []
for k, r in enumerate(RADII):
    K = lambda c: A * c / (N * (N - 1)) / 1e6; ka, kbb = [K(v) for v in prA[k]], [K(v) for v in prB[k]]
    kb.append([r, pairs[k], K(pairs[k]), math.sqrt(K(pairs[k]) * 1e6 / math.pi), sum(ka) / SIMS, sum(kbb) / SIMS, K(pairs[k]) / (sum(ka) / SIMS), K(pairs[k]) / (sum(kbb) / SIMS),
               K(pairs[k]) / max(ka), K(pairs[k]) / max(kbb)])
compare_table("kfunction.csv", kb)

# ---- cuisine, chains
compare_table("cuisine.csv", [[c, v, v / tagged] for c, v in sorted(cc.items(), key=lambda kv: (-kv[1], kv[0]))[:30]])
chb = []
for m in (3, 5, 10, 20):
    ch = set(k for k, v in nc.items() if v >= m); pl = [p for p in named if p["nname"] in ch]
    chb.append([m, len(ch), len(pl), len(pl) / len(named), len(pl) / N, sum(p["brand"] for p in pl)])
compare_table("chains.csv", chb)
compare_table("chain_names.csv", [[k, v, brand_name[k]] for k, v in sorted(((k, v) for k, v in nc.items() if v >= CHAIN_N), key=lambda kv: (-kv[1], kv[0]))[:20]])

# ---- stability
sb = []
for lab, ts in DEFS.items():
    S = [p for p in P if p["type"] in ts]; ns = len(S); dS = nnd if ts is TYPES else brute([(p["x"], p["y"]) for p in S])[0]; mS = sum(dS) / ns
    nm = Counter(p["nname"] for p in S if p["name_f"]); chs = set(k for k, v in nm.items() if v >= CHAIN_N)
    ms = simA("A-all" if ts is TYPES else "A-" + lab, ns)[0]
    sb.append([lab, ns, sum(p["d"] < 5000 for p in S), sum(p["nname"] in chs for p in S if p["name_f"]), sum(p["name_f"] for p in S), sum(bool(p["cuis"]) for p in S), mS, mS / (0.5 * math.sqrt(A / ns)), mS / (sum(ms) / SIMS)])
compare_table("stability.csv", sb)
print(f"check.py: {n_ok} recomputed numbers agree with results/")
