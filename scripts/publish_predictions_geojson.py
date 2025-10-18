#!/usr/bin/env python3
# Minimal local “publish” for logistic regression → GeoJSON (+ latest.json + quicklook)

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import matplotlib.pyplot as plt


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", default="2025-10-17", help="Prediction date folder name (YYYY-MM-DD)")
    p.add_argument("--pred_dir", default="predictions", help="Root predictions directory")
    p.add_argument("--parquet", default=None, help="Parquet filename in the date folder (auto-detect if omitted)")
    p.add_argument("--prob_col", default="p_logistic", help="Probability column to publish")
    p.add_argument("--lon_col", default="x", help="Longitude column (degrees, WGS84)")
    p.add_argument("--lat_col", default="y", help="Latitude column (degrees, WGS84)")
    args = p.parse_args()

    date_dir = Path(args.pred_dir) / args.date
    date_dir.mkdir(parents=True, exist_ok=True)

    # 1) Locate parquet
    if args.parquet:
        pq_path = date_dir / args.parquet
    else:
        # Prefer a dated parquet, else any *.parquet
        cand = list(date_dir.glob(f"*{args.date}*.parquet")) or list(date_dir.glob("*.parquet"))
        if not cand:
            raise FileNotFoundError(f"No parquet found in {date_dir}")
        pq_path = cand[0]

    # 2) Load & sanity checks
    df = pd.read_parquet(pq_path)
    for c in (args.lon_col, args.lat_col, args.prob_col):
        if c not in df.columns:
            raise KeyError(f"Missing required column '{c}' in {pq_path.name}")
    if df[args.lon_col].abs().max() > 200 or df[args.lat_col].abs().max() > 90:
        raise ValueError("Lon/lat columns don’t look like degrees. Check CRS or column names.")

    # Optional attributes to bring into popups if present
    popup_candidates = [
        "row", "col",
        "R1d", "R3d", "R7d", "R30d", "Max_Rainfall_3day", "Max_Rainfall_30day"
    ]
    keep_cols = []
    for c in ["row", "col", args.prob_col] + popup_candidates:
        if c in df.columns and c not in keep_cols:
            keep_cols.append(c)

    # 3) Build GeoDataFrame (WGS84)
    gdf = gpd.GeoDataFrame(
        df[keep_cols].copy(),
        geometry=[Point(lon, lat) for lon, lat in zip(df[args.lon_col], df[args.lat_col])],
        crs="EPSG:4326",
    )
    print("keep_cols:", keep_cols)
    print("gdf.columns:", list(gdf.columns))
    dups = gdf.columns[gdf.columns.duplicated()]
    print("duplicates:", list(dups))

    # 4) Write GeoJSON into the dated folder
    out_geojson = date_dir / "predictions.geojson"
    gdf.to_file(out_geojson, driver="GeoJSON")

    # 5) Update "latest" pointers
    latest_geojson = Path(args.pred_dir) / "latest.geojson"
    shutil.copyfile(out_geojson, latest_geojson)

    # meta summary (latest.json)
    latest_json = Path(args.pred_dir) / "latest.json"
    meta = {
        "target_date": args.date,
        "model": "logistic",
        "prob_col": args.prob_col,
        "rows": int(len(gdf)),
        "source_parquet": pq_path.name,
        "fields": keep_cols,
    }
    with latest_json.open("w") as f:
        json.dump(meta, f, indent=2)

    # 6) Quicklook PNG (simple scatter by probability)
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    png_path = reports_dir / f"quicklook_{args.date}_logistic.png"

    fig, ax = plt.subplots(figsize=(8, 8))
    import matplotlib.colors as mcolors

    # smooth colormap: blue → teal → green → yellow → orange → red
    colors = [
        (0.2, 0.4, 0.8),  # deep blue
        (0.1, 0.7, 0.7),  # teal
        (0.3, 0.8, 0.4),  # green
        (0.9, 0.9, 0.2),  # yellow
        (0.98, 0.6, 0.2),  # orange
        (0.8, 0.1, 0.1)  # red
    ]
    cmap = mcolors.LinearSegmentedColormap.from_list("smooth_046", colors, N=256)

    fig, ax = plt.subplots(figsize=(8, 8))
    sc = ax.scatter(
        df[args.lon_col],
        df[args.lat_col],
        c=df[args.prob_col],
        s=6,
        alpha=0.9,
        vmin=0.4,
        vmax=0.6,
        cmap=cmap,
    )
    cbar = plt.colorbar(sc, ax=ax, shrink=0.8)
    cbar.set_label(f"{args.prob_col} (0.4–0.6 range)")
    ax.set_title(f"Buncombe risk • through {args.date} • model: LOGISTIC")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal", adjustable="box")
    plt.tight_layout()
    fig.savefig(png_path, dpi=200)
    plt.close(fig)

    plt.close(fig)

    print(f"[ok] GeoJSON: {out_geojson}")
    print(f"[ok] Latest pointer: {latest_geojson}")
    print(f"[ok] Meta: {latest_json}")
    print(f"[ok] Quicklook: {png_path}")


if __name__ == "__main__":
    main()
