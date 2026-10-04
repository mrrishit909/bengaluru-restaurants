"""Step 6: charts.   ~/tools/venv/bin/python charts.py -> charts/00_cover.png, 01_density.png, 02_clustering.png, 03_cuisine_chains.png, 04_completeness.png, 05_stability.png

Aggregates only: 1 km cell counts, ring densities, summary statistics. The boundary outline is drawn from data/boundary.json (run download.py first).
Map data (c) OpenStreetMap contributors, ODbL."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, PowerNorm

from analyze import load

HERE = Path(__file__).parent
R = HERE / "results"
INK, DIM, GRID, BG, BLUE, ORANGE, GRAY, GREEN = "#f2f2f0", "#8a8a87", "#1d1d1d", "#0b0b0b", "#3987e5", "#d95926", "#9a9a96", "#3aa876"
plt.rcParams.update({"figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG, "text.color": INK,
                     "axes.edgecolor": "#3a3a3a", "axes.labelcolor": DIM, "xtick.color": DIM, "ytick.color": DIM,
                     "axes.grid": True, "axes.axisbelow": True, "grid.color": GRID, "grid.linewidth": 1,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "font.family": ["Helvetica Neue", "Arial", "DejaVu Sans"], "font.size": 11, "axes.titlesize": 13,
                     "axes.titlelocation": "left", "axes.titlepad": 12})
CELLS = pd.read_csv(R / "cells.csv"); RINGS = pd.read_csv(R / "rings.csv"); TY = pd.read_csv(R / "types.csv").set_index("amenity"); CL = pd.read_csv(R / "clustering.csv").set_index("key")["value"]
KF = pd.read_csv(R / "kfunction.csv"); CU = pd.read_csv(R / "cuisine.csv"); CN = pd.read_csv(R / "chain_names.csv"); ST = pd.read_csv(R / "stability.csv"); SM = pd.read_csv(R / "summary.csv").set_index("key")["value"]
AU = pd.read_csv(R / "audit.csv").set_index("check")["value"]
RINGS["per_km2"] = RINGS["places"] / RINGS["area_km2"]; RING_LAB = ["0-2", "2-5", "5-10", "10-15", "15+"]
_, RINGS_XY, _, _ = load()


def save(fig, name):
    fig.tight_layout(); fig.savefig(HERE / "charts" / name, dpi=150); plt.close(fig)


def heat(ax, fs=9):
    cmap = LinearSegmentedColormap.from_list("h", ["#12233d", BLUE, "#9ec5f2", INK])
    x0, y0 = CELLS["cx"].min(), CELLS["cy"].min(); g = np.full((CELLS["cy"].max() - y0 + 1, CELLS["cx"].max() - x0 + 1), np.nan)
    for cx, cy, n in CELLS.itertuples(index=False): g[cy - y0, cx - x0] = n
    im = ax.imshow(g, origin="lower", extent=(x0, CELLS["cx"].max() + 1, y0, CELLS["cy"].max() + 1), cmap=cmap, norm=PowerNorm(0.5, vmin=1, vmax=150), interpolation="nearest")
    for r in RINGS_XY: ax.plot([p[0] / 1000 for p in r], [p[1] / 1000 for p in r], color=DIM, linewidth=0.8)
    for rad in (5, 10, 15):
        ax.add_patch(plt.Circle((0, 0), rad, fill=False, color=DIM, linestyle=":", linewidth=0.8)); ax.text(0.4, -rad + 0.4, f"{rad} km", color=DIM, fontsize=8)
    ax.scatter([0], [0], color=ORANGE, s=26, zorder=4); ax.text(-0.8, 0.9, "centre", color=ORANGE, fontsize=fs, ha="right")
    ax.set_aspect("equal"); ax.grid(False); ax.set_xlabel("km east of the centre"); ax.set_ylabel("km north of the centre")
    cb = plt.colorbar(im, ax=ax, fraction=0.04, pad=0.02, ticks=[1, 5, 25, 75, 150]); cb.ax.set_yticklabels(["1", "5", "25", "75", "150+"]); cb.ax.tick_params(labelsize=8, colors=DIM); cb.outline.set_edgecolor("#3a3a3a")
    cb.set_label("places in a 1 km cell", color=DIM, fontsize=9)


def density_bars(ax, fs=10):
    x = np.arange(5); v = RINGS["per_km2"]; ax.bar(x, v, color=BLUE, width=0.6)
    for xi, vi, n in zip(x, v, RINGS["places"]): ax.text(xi, vi + 1, f"{vi:.0f}", ha="center", fontsize=fs + 1, color=INK); ax.text(xi, -5.2, f"{n:,} places", ha="center", fontsize=8, color=DIM)
    ax.set_xticks(x); ax.set_xticklabels([f"{r} km" for r in RING_LAB], fontsize=9.5); ax.set_ylim(0, 56); ax.set_ylabel("places per km²"); ax.set_xlabel("distance from the centre", labelpad=18); ax.grid(axis="x", visible=False)
    ax.axhline(AU["places analysed"] / AU["area, km2 (shoelace)"], color=ORANGE, linestyle="--", linewidth=1.3); ax.text(4.4, AU["places analysed"] / AU["area, km2 (shoelace)"] + 1, f"whole city: {AU['places analysed'] / AU['area, km2 (shoelace)']:.1f}", color=ORANGE, fontsize=9, ha="right")


def share_bars(ax):
    x = np.arange(5); w = 0.38; a = 100 * RINGS["area_km2"] / RINGS["area_km2"].sum(); p = 100 * RINGS["places"] / RINGS["places"].sum()
    ax.bar(x - w / 2, a, width=w * 0.92, color=GRAY, label="share of the area"); ax.bar(x + w / 2, p, width=w * 0.92, color=BLUE, label="share of the places")
    for xi, v in list(zip(x - w / 2, a)) + list(zip(x + w / 2, p)): ax.text(xi, v + 0.8, f"{v:.0f}%", ha="center", fontsize=8.5, color=INK)
    ax.set_xticks(x); ax.set_xticklabels([f"{r} km" for r in RING_LAB], fontsize=9.5); ax.set_ylim(0, 56); ax.set_ylabel("% of the city"); ax.set_xlabel("distance from the centre"); ax.legend(frameon=False, labelcolor=INK, fontsize=9, loc="upper left"); ax.grid(axis="x", visible=False)


def nn_bars(ax, fs=10):
    labs = ["the data", "random points\nin the city", "random points, same\ncount in each 1 km cell"]
    v = [CL["mean nearest-neighbour distance, m"], CL["A uniform: mean of the simulated mean distances, m"], CL["B same count per 1 km cell: mean of the simulated mean distances, m"]]
    ax.bar(range(3), v, color=[BLUE, GRAY, GRAY], width=0.6)
    for i, vi in enumerate(v): ax.text(i, vi + 3, f"{vi:.0f} m", ha="center", fontsize=fs + 1, color=INK)
    ax.set_xticks(range(3)); ax.set_xticklabels(labs, fontsize=9); ax.set_ylim(0, 195); ax.set_ylabel("mean distance to the nearest other place (m)"); ax.grid(axis="x", visible=False)


def k_bars(ax, fs=9):
    x = np.arange(4); w = 0.38; ax.bar(x - w / 2, KF["K_over_A"], width=w * 0.92, color=BLUE, label="against random points in the city"); ax.bar(x + w / 2, KF["K_over_B"], width=w * 0.92, color=ORANGE, label="against random points, same count per 1 km cell")
    for xi, v in list(zip(x - w / 2, KF["K_over_A"])) + list(zip(x + w / 2, KF["K_over_B"])): ax.text(xi, v + 0.4, f"{v:.1f}", ha="center", fontsize=fs, color=INK)
    ax.axhline(1, color=INK, linestyle="--", linewidth=1, label="random = 1")
    ax.set_xticks(x); ax.set_xticklabels([f"{r} m" for r in KF["radius_m"]]); ax.set_ylim(0, 27); ax.set_xlabel("radius r"); ax.set_ylabel("pairs within r, data ÷ random"); ax.legend(frameon=False, labelcolor=INK, fontsize=8.5, loc="upper right"); ax.grid(axis="x", visible=False)


def cuisine(ax, k=12, fs=9.5):
    d = CU.head(k); y = np.arange(k); ax.barh(y, 100 * d["share_of_tagged"], color=BLUE, height=0.65)
    for yi, v, n in zip(y, 100 * d["share_of_tagged"], d["places"]): ax.text(v + 0.4, yi, f"{v:.0f}%  ({n})", va="center", fontsize=fs - 1, color=INK)
    ax.set_yticks(y); ax.set_yticklabels([c.replace("_", " ") for c in d["cuisine"]], fontsize=fs); ax.invert_yaxis(); ax.set_xlim(0, 26); ax.set_xlabel("% of the places that have a cuisine tag"); ax.grid(axis="y", visible=False)


def chains(ax, k=12, fs=9.5):
    d = CN.head(k); y = np.arange(k); ax.barh(y, d["places"], color=ORANGE, height=0.65)
    for yi, v in zip(y, d["places"]): ax.text(v + 1.5, yi, str(v), va="center", fontsize=fs - 0.5, color=INK)
    ax.set_yticks(y); ax.set_yticklabels([n.title().replace("Dominos", "Domino's").replace("Mcdonalds", "McDonald's").replace("Kfc", "KFC").replace("Baskinrobbins", "Baskin-Robbins") for n in d["name"]], fontsize=fs)
    ax.invert_yaxis(); ax.set_xlim(0, 125); ax.set_xlabel("places on the map"); ax.grid(axis="y", visible=False)


def completeness_types(ax, fs=8.5):
    names = ["restaurant", "fast_food", "cafe", "pub", "all"]; flags = [("cuisine", BLUE), ("opening_hours", GREEN), ("phone", ORANGE), ("website", GRAY)]; x = np.arange(len(names)); w = 0.2
    for k, (f, c) in enumerate(flags):
        v = [100 * TY.loc[t, f] / TY.loc[t, "places"] for t in names]; ax.bar(x + (k - 1.5) * w, v, width=w * 0.92, color=c, label=f.replace("_", " "))
        for xi, vi in zip(x + (k - 1.5) * w, v): ax.text(xi, vi + 0.8, f"{vi:.0f}", ha="center", fontsize=7.5, color=INK)
    ax.set_xticks(x); ax.set_xticklabels(["restaurant", "fast food", "cafe", "pub", "all places"], fontsize=9); ax.set_ylim(0, 62); ax.set_ylabel("% of places with the tag"); ax.legend(frameon=False, labelcolor=INK, fontsize=fs, loc="upper right", ncol=2); ax.grid(axis="x", visible=False)


def completeness_rings(ax, fs=8.5):
    flags = [("cuisine", BLUE), ("opening_hours", GREEN), ("phone", ORANGE), ("website", GRAY)]; x = np.arange(5); w = 0.2
    for k, (f, c) in enumerate(flags):
        v = 100 * RINGS[f] / RINGS["places"]; ax.bar(x + (k - 1.5) * w, v, width=w * 0.92, color=c, label=f.replace("_", " "))
        for xi, vi in zip(x + (k - 1.5) * w, v): ax.text(xi, vi + 0.8, f"{vi:.0f}", ha="center", fontsize=7.5, color=INK)
    ax.set_xticks(x); ax.set_xticklabels([f"{r} km" for r in RING_LAB], fontsize=9); ax.set_ylim(0, 62); ax.set_ylabel("% of places with the tag"); ax.set_xlabel("distance from the centre"); ax.legend(frameon=False, labelcolor=INK, fontsize=fs, loc="upper right", ncol=2); ax.grid(axis="x", visible=False)


def stability(axes, fs=9):
    ax = axes[0]; x = np.arange(3); w = 0.26; labs = ["restaurant\nonly", "restaurant,\nfast food, cafe", "all seven\ntypes"]
    for k, (col, lab, c) in enumerate((("within_5km", "within 5 km of the centre", BLUE), ("cuisine_tagged", "has a cuisine tag", GREEN), ("chain_places", "belongs to a chain (of named)", ORANGE))):
        den = ST["named"] if col == "chain_places" else ST["places"]; v = 100 * ST[col] / den
        ax.bar(x + (k - 1) * w, v, width=w * 0.92, color=c, label=lab)
        for xi, vi in zip(x + (k - 1) * w, v): ax.text(xi, vi + 0.8, f"{vi:.0f}%", ha="center", fontsize=8.5, color=INK)
    ax.set_xticks(x); ax.set_xticklabels(labs, fontsize=8.5); ax.set_ylim(0, 72); ax.set_ylabel("% of places"); ax.legend(frameon=False, labelcolor=INK, fontsize=8.5, loc="upper left"); ax.grid(axis="x", visible=False); ax.set_title("Shares by definition", fontsize=12)
    ax = axes[1]; ax.bar(x, ST["R_vs_simulated"], color=BLUE, width=0.55)
    for xi, vi, n in zip(x, ST["R_vs_simulated"], ST["places"]): ax.text(xi, vi + 0.02, f"{vi:.2f}", ha="center", fontsize=fs + 1, color=INK); ax.text(xi, 0.04, f"{n:,}\nplaces", ha="center", fontsize=8, color=BG)
    ax.axhline(1, color=ORANGE, linestyle="--", linewidth=1.3); ax.text(2.4, 1.02, "random = 1", color=ORANGE, fontsize=9, ha="right")
    ax.set_xticks(x); ax.set_xticklabels(labs, fontsize=8.5); ax.set_ylim(0, 1.15); ax.set_ylabel("Clark-Evans R (against random points)"); ax.grid(axis="x", visible=False); ax.set_title("Clustering by definition", fontsize=12)


def main():
    (HERE / "charts").mkdir(exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(14, 8), gridspec_kw={"width_ratios": [1.15, 1]})
    heat(axes[0], 10); axes[0].set_title("Places per 1 km cell", fontsize=12); density_bars(axes[1], 11); axes[1].set_title("Places per km², by distance from the centre", fontsize=12)
    r = RINGS["per_km2"]
    fig.suptitle(f"Bengaluru's food places on OpenStreetMap crowd the centre: {r[0]:.0f} per km² within 2 km, {r[4]:.0f} beyond 15 km, and far closer together than chance", x=0.01, ha="left", fontsize=20, color=INK, y=0.98, wrap=True)
    fig.tight_layout(rect=(0, 0, 1, 0.94)); fig.savefig(HERE / "charts" / "00_cover.png", dpi=100); plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.3), gridspec_kw={"width_ratios": [1.15, 1]}); heat(axes[0]); axes[0].set_title("Where the places are", fontsize=12); share_bars(axes[1]); axes[1].set_title("Centre against area", fontsize=12); save(fig, "01_density.png")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2)); nn_bars(axes[0]); axes[0].set_title("Nearest neighbour", fontsize=12); k_bars(axes[1]); axes[1].set_title("Ripley's K, data against random", fontsize=12); save(fig, "02_clustering.png")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.3)); cuisine(axes[0]); axes[0].set_title("Top cuisines", fontsize=12); chains(axes[1]); axes[1].set_title("Biggest chains by name", fontsize=12); save(fig, "03_cuisine_chains.png")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2)); completeness_types(axes[0]); axes[0].set_title("How much is described, by type", fontsize=12); completeness_rings(axes[1]); axes[1].set_title("... and by distance from the centre", fontsize=12); save(fig, "04_completeness.png")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2)); stability(axes); save(fig, "05_stability.png")


if __name__ == "__main__":
    main()
