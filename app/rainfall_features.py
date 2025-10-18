"""Utilities for rainfall feature extraction and aggregation."""
from __future__ import annotations

import datetime as dt
import zipfile
from pathlib import Path
from typing import Dict, Iterable, Tuple

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio import features
import yaml


ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / "config.yaml").read_text())
RAIN_DIR = ROOT / CFG["paths"]["rainfall_dir"]
COUNTY_SHP = ROOT / "data/static/cb_2022_us_county_500k.shp"

FEATURE_COLUMNS = (
    "R1d",
    "R3d",
    "R7d",
    "R30d",
    "Max_Rainfall_3day",
    "Max_Rainfall_30day",
)


def available_dates() -> list[dt.date]:
    """Return sorted dates inferred from files in the rainfall directory."""

    dates: set[dt.date] = set()
    for entry in RAIN_DIR.iterdir():
        stem = entry.stem if entry.is_file() else entry.name
        if not stem.startswith("prism_ppt_us_30s_"):
            continue
        candidate = stem.split("prism_ppt_us_30s_")[-1]
        try:
            dates.add(dt.datetime.strptime(candidate, "%Y%m%d").date())
        except ValueError:
            continue
    return sorted(dates)


def resolve_target_date(requested: dt.date) -> dt.date:
    """Return the latest available rainfall date not after ``requested``."""

    dates = available_dates()
    if not dates:
        raise FileNotFoundError(f"No rainfall rasters found in {RAIN_DIR}")

    if requested < dates[0]:
        return dates[0]

    for day in reversed(dates):
        if day <= requested:
            return day

    return dates[-1]


def _resolve_day_path(day: dt.date) -> str | None:
    stamp = day.strftime("%Y%m%d")
    directory = RAIN_DIR / f"prism_ppt_us_30s_{stamp}"
    if directory.is_dir():
        tifs = sorted(directory.glob("*.tif"))
        if tifs:
            return str(tifs[0])

    zipped = RAIN_DIR / f"prism_ppt_us_30s_{stamp}.zip"
    if zipped.exists():
        with zipfile.ZipFile(zipped) as zf:
            for name in zf.namelist():
                if name.lower().endswith(".tif"):
                    return f"zip://{zipped}!{name}"

    tif = RAIN_DIR / f"prism_ppt_us_30s_{stamp}.tif"
    if tif.exists():
        return str(tif)

    return None


def _load_stack(target: dt.date, window: int) -> Tuple[np.ndarray, dict]:
    ref_path = _resolve_day_path(target)
    if ref_path is None:
        raise FileNotFoundError(f"No rainfall raster for {target} under {RAIN_DIR}")

    with rasterio.open(ref_path) as ref:
        meta = ref.meta.copy()
        template = ref.read(1).astype(np.float32)

    stack: list[np.ndarray] = []

    for delta in range(window - 1, -1, -1):
        day = target - dt.timedelta(days=delta)
        path = _resolve_day_path(day)
        if path is None:
            stack.append(np.zeros_like(template))
            continue
        with rasterio.open(path) as src:
            stack.append(src.read(1).astype(np.float32))

    return np.stack(stack, axis=0), meta


def _load_mask(meta: dict) -> np.ndarray:
    if not COUNTY_SHP.exists():
        return np.ones((meta["height"], meta["width"]), dtype=bool)

    gdf = gpd.read_file(COUNTY_SHP)
    buncombe = gdf[gdf["GEOID"] == "37021"]
    if buncombe.empty:
        return np.ones((meta["height"], meta["width"]), dtype=bool)

    geom = buncombe.to_crs(meta["crs"]).geometry.iloc[0]
    mask = features.rasterize(
        [(geom, 1)],
        out_shape=(meta["height"], meta["width"]),
        transform=meta["transform"],
        fill=0,
        dtype="uint8",
    )
    return mask.astype(bool)


def _sum_last(stack: np.ndarray, days: int) -> np.ndarray:
    return stack[-min(days, stack.shape[0]) :].sum(axis=0)


def _max_last(stack: np.ndarray, days: int) -> np.ndarray:
    return stack[-min(days, stack.shape[0]) :].max(axis=0)


def compute_feature_arrays(
    target: dt.date, window: int
) -> Tuple[Dict[str, np.ndarray], np.ndarray, dict, dt.date]:
    """Compute rainfall feature arrays and mask, snapping to available data."""

    resolved = resolve_target_date(target)
    stack, meta = _load_stack(resolved, window)
    features = {
        "R1d": stack[-1],
        "R3d": _sum_last(stack, 3),
        "R7d": _sum_last(stack, 7),
        "R30d": _sum_last(stack, 30),
        "Max_Rainfall_3day": _max_last(stack, 3),
        "Max_Rainfall_30day": _max_last(stack, 30),
    }
    mask = _load_mask(meta)
    return features, mask, meta, resolved


def feature_means(target: dt.date, window: int) -> Tuple[dict[str, float], dt.date]:
    arrays, mask, _, resolved = compute_feature_arrays(target, window)
    means: dict[str, float] = {}
    for name in FEATURE_COLUMNS:
        data = np.where(mask, arrays[name], np.nan)
        means[name] = float(np.nanmean(data))
    return means, resolved


def build_rainfall_frame(
    target: dt.date,
    cell_ids: Iterable,
    window: int = 30,
) -> Tuple[pd.DataFrame, dt.date]:
    """Return rainfall features repeated for ``cell_ids`` and the actual end date used."""

    means, resolved = feature_means(target, window)
    data = {col: np.repeat(means[col], len(cell_ids)) for col in FEATURE_COLUMNS}
    df = pd.DataFrame(data)
    df.insert(0, "cell_id", list(cell_ids))
    return df, resolved
