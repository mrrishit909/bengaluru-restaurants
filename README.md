# Where do Bengaluru's food places cluster?

The restaurants, cafes, fast-food places, bars, pubs, food courts and ice-cream shops of Bengaluru as mapped in OpenStreetMap, 6,681 of them in the 719 km2 of the city's administrative boundary. Five questions:
- where they are: how density falls from the centre to the edge, and how concentrated the busiest 1 km cells are;
- whether they cluster more than random points would, and more than the uneven density of the city alone explains (a nearest-neighbour statistic and Ripley's K, both computed here against simulated random points);
- what they serve: how many carry a cuisine tag and which cuisines are most common;
- chains against independents, by how often a name repeats;
- how much of the map is described (cuisine, opening hours, phone, website), and how much of all this changes with the definition of a "food place".

The questions follow GeeksforGeeks' "Zomato Data Analysis". The usual file for that task is scraped Zomato listings of Bangalore restaurants (ratings, prices, votes); that file is not used, because scraping Zomato is not allowed here and the data are not open. OpenStreetMap, the open map built by volunteers, is the stand-in: it has the places, their locations and some descriptive tags, but **no ratings and no prices**. The page with the results and the charts is the build log:

Build log: https://mrrishit909.github.io/projects/bengaluru-restaurants/

## Data

OpenStreetMap, through the Overpass API (https://overpass-api.de/api/interpreter), two queries with the User-Agent `research-portfolio (Rishit Raj Mathur)`: every node and way tagged `amenity` = restaurant, cafe, fast_food, bar, pub, food_court or ice_cream inside OSM relation 7902476 "Bengaluru" (operated by the Greater Bengaluru Authority), and the geometry of that relation. The OSM database timestamp of the answers is 2026-10-04 05:43:21 UTC; the files are 2.2 MB (checksums in `results/pull.json`) and are not committed. The Overpass usage policy asks for fewer than 10,000 queries and 1 GB a day; each run of `download.py` makes 2. Licence: data (c) OpenStreetMap contributors, Open Database Licence (ODbL) 1.0, https://www.openstreetmap.org/copyright. The tables in `results/` are derived from that data and are offered under the same licence, (c) OpenStreetMap contributors; they hold aggregates only.

```
~/tools/venv/bin/pip install numpy scipy pandas matplotlib certifi      # in a venv
./venv/bin/python download.py    # data/*  (2 Overpass queries)
./venv/bin/python analyze.py     # results/*  (about 30 seconds)
./venv/bin/python check.py       # about 40 seconds
./venv/bin/python charts.py
```

## Steps

1. **Download** the places and the boundary relation, with checksums. OSM changes every minute: a first pull returned 6,680 elements and a second one a minute later 6,682, so the files in `data/` were frozen and every result comes from them.
2. **Audit.** The boundary's 51 outer ways are stitched into closed rings (1 ring, 4,980 vertices, 719.1 km2 by the shoelace formula, 718.8 on a 250 m raster); every place is tested against that polygon by ray casting, and 1 whose centre falls outside is dropped. The centre is the relation's own `admin_centre` node. Names without a name, cuisine values with a comma, and probable duplicates (same name within 50 m) are counted.
3. **Density.** Places per 1 km cell, the share in the busiest 5% of occupied cells, and places per km2 in rings 0-2, 2-5, 5-10, 10-15 and 15+ km from the centre.
4. **Clustering.** The distance from every place to its nearest neighbour (Clark-Evans R) and Ripley's K at 100, 250, 500 and 1,000 m, against 19 simulated sets of random points of the same size inside the same polygon, and 19 sets with the same number of random points as the data in each 1 km cell.
5. **Cuisine, chains, tags.** The cuisine tag split on ';'; a chain is a name (lower-cased, punctuation dropped) that occurs at least 5 times; completeness of name, cuisine, opening_hours, phone and website by type and by ring; the same headline numbers for three definitions of a food place.
6. **Check.** `check.py` recomputes everything in plain Python (json, csv, math and loops: no pandas, numpy, scipy or shapely): the polygon stitched another way, every one of the 6,681 places tested by another ray-casting routine, nearest neighbours and pair counts by brute force over all 22,314,540 pairs, the random sets redrawn from the same seeds: 1,881 numbers to a relative tolerance of 1e-9.
7. **Charts.**

## Results

- **6,681 places in 719 km2**, 9.3 per km2 on average: 3,168 restaurants, 1,724 fast-food places, 1,115 cafes, 240 pubs, 195 ice-cream shops, 191 bars and 48 food courts.
- **The centre is dense, but most places are mid-ring.** Per km2: 47 at 0-2 km, 15 at 2-5 km, 13 at 5-10 km, 5 at 10-15 km, 4 at 15+ km. The 5 km around the centre is 11% of the area and holds 24% of the places; the 5-10 km ring alone holds 47%. The median place is 7.0 km from the centre, the median point of the city 10.7 km. The busiest 5% of the 489 occupied 1 km cells hold 33% of the places; the busiest cell, 1 to 2 km east and up to 1 km south of the centre (its address tags say Brigade Road, Church Street and Mahatma Gandhi Road), holds 261.
- **They sit much closer together than random points.** The mean distance to the nearest other place is 60 m (median 24 m); for random points in the city it is 165 m, so Clark-Evans R = 0.36 (analytic: 0.36), and none of the 19 simulated sets comes close (163 to 167 m). Ripley's K counts 22 times as many pairs within 100 m as random points do, 6 times within 500 m and 4 times within 1 km.
- **Most of that is the uneven city, but not all.** Random points with the same count in each 1 km cell have a mean nearest-neighbour distance of 115 m (R = 0.52; again 0 of 19 sets reach the data's) and the data has 4.3 times as many pairs within 100 m as those sets, 2.0 times within 250 m, 1.4 within 500 m and 1.1 within 1 km. So places cluster on a street scale of a few hundred metres, beyond where the 1 km density puts them. Main roads, malls and food courts, and mappers surveying a street at a time are plausible reasons; none was tested.
- **What they serve.** 45% of the places have a cuisine tag (188 distinct values, 80 used once). Of those, indian 20%, regional 18%, coffee shop 12%, pizza 9%, burger 7%, chinese 5%, juice 5%, chicken 4%; a place with several cuisines counts under each. "Regional" is a catch-all and says little.
- **Chains.** 111 names occur at least 5 times, on 1,400 places: 21% of the named places (14% for names occurring at least 10 times, 29% at least 3). The biggest: Domino's 106, Cafe Coffee Day 75, Indira Canteen 58, KFC 49, McDonald's 47. The chain share of named places rises from 16% within 2 km of the centre to 25% beyond 15 km. 817 of the 1,400 chain places also carry a brand tag.
- **How much of the map is described.** 98% have a name, 45% a cuisine, 11.5% opening hours, 8.9% a phone number, 7.5% a website, and 123 (1.8%) all five. Restaurants are best described (15% with opening hours, 14% a phone), fast-food places least (6%, 3%); bars and food courts carry no cuisine tag at all. By distance, the cuisine share is flat (42% to 47%), but opening hours go from 14% at 2-5 km to 6% beyond 15 km.
- **Stable across the definition, except the chain share.** Restaurants only (3,168), restaurants, fast food and cafes (6,007) and all seven types: 23%, 24% and 24% lie within 5 km of the centre, and R against random points is 0.41, 0.37 and 0.36. The chain share of named places is 11%, 22% and 21%: the chain share doubles once fast food and cafes are added.
- **Traps.** 47 pairs of places with the same name lie within 50 m of each other (88 places, 1.3%; 6 of the pairs are a node and a way), kept in every count; 11 places sit exactly on another's coordinates (food-court stalls, stacked nodes); 126 have no name; 3 cuisine tags use a comma instead of ';'.

## Not done, and caveats

- OpenStreetMap is volunteer-mapped and its coverage is uneven in space and by type. A place missing from the map is not a missing restaurant, and density here measures mapping effort as well as eating out; the fall from the centre to the edge mixes both. The counts are not a census and no claim is made about how many food places Bengaluru has.
- There are no ratings, prices, reviews or footfall in OpenStreetMap, so nothing here says which places are good or busy. The Zomato file the original task uses is not used.
- Only the seven `amenity` values above, as nodes and ways; multipolygon relations tagged with them were not queried, nor were `shop=bakery`, `amenity=canteen`, `biergarten` or untagged street food. A way's position is the centre of its bounding box, as Overpass returns it, not its centroid.
- The study area is OSM's relation for Bengaluru (the Greater Bengaluru Authority area, 719 km2), not the metropolitan region; the projection is equirectangular about the admin centre (about 0.1% error over 40 km). The centre is one point; "centre" and "periphery" are distances from it.
- Clark-Evans R and K are descriptive and carry no edge correction; the simulated sets are drawn in the same polygon, so the edge bias is in both. Only 19 sets are drawn per baseline, so "0 of 19" resolves p only to 1 in 20. The second baseline controls the density of 1 km cells, not roads, buildings or mapping habits, so excess clustering beyond it is not evidence of any cause.
- Chains are exact repeats of a normalised name: spelling variants (for example "Third Wave Coffee Roasters" and "Third Wave Coffee") count as different names, so the chain share is a lower bound, and a repeated generic name would count as a chain. Only brand names are listed; no independent place is named.
- A missing tag means the volunteers did not add it, not that a place has no phone or no opening hours. `cuisine=regional` is vague.
- OSM changes every minute; a rerun of `download.py` returns slightly different data (checksums and timestamp in `results/pull.json`).
- Nothing from the raw data is committed, only summaries; the licence is as above.
