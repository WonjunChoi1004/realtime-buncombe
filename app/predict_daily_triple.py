#!/usr/bin/env python3
"""Generate wildfire probability predictions on the rainfall grid."""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import joblib
import numpy as np
import pandas as pd
import rasterio
from rasterio import features
from rasterio.warp import transform as warp_transform
import yaml

ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / "config.yaml").read_text())

DATE_FMT = "%Y-%m-%d"
RAIN_DIR = ROOT / CFG["paths"]["rainfall_dir"]
PRED_DIR = ROOT / CFG["paths"]["predictions_dir"]
MODELS_DIR = ROOT / CFG["paths"]["models_dir"]
STATIC_PARQ = ROOT / CFG["paths"]["static_grid"]
RAIN_WINDOW_DAYS = 30
RAIN_FALLBACK_CRS = "EPSG:4269"

STATIC_COLS = CFG["columns"]
FEATURE_NAME_MAP = {"elevation_m": "Elevation_m", "slope_deg": "Slope_deg"}
RAIN_FEATURES = [
    "R1d",
    "R3d",
    "R7d",
    "R30d",
    "Max_Rainfall_3day",
    "Max_Rainfall_30day",
]
PRED_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Rainfall helpers
# ---------------------------------------------------------------------------

def _available_dates() -> List[dt.date]:
    dates: set[dt.date] = set()
    for entry in RAIN_DIR.iterdir():
        stem = entry.stem if entry.is_file() else entry.name
        if not stem.startswith("prism_ppt_us_30s_"):
            continue
        suffix = stem.split("prism_ppt_us_30s_")[-1]
        try:
            dates.add(dt.datetime.strptime(suffix, "%Y%m%d").date())
        except ValueError:
            continue
    return sorted(dates)


def _resolve_target_date(requested: dt.date) -> dt.date:
    dates = _available_dates()
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
    folder = RAIN_DIR / f"prism_ppt_us_30s_{stamp}"
    if folder.is_dir():
        tifs = sorted(folder.glob("*.tif"))
        if tifs:
            return str(tifs[0])
    zipped = RAIN_DIR / f"prism_ppt_us_30s_{stamp}.zip"
    if zipped.exists():
        return f"zip://{zipped}!prism_ppt_us_30s_{stamp}.tif"
    tif = RAIN_DIR / f"prism_ppt_us_30s_{stamp}.tif"
    if tif.exists():
        return str(tif)
    return None


def _collect_day_paths(target: dt.date, window: int) -> List[Tuple[dt.date, str | None]]:
    resolved = _resolve_target_date(target)
    days = [resolved - dt.timedelta(days=i) for i in range(window - 1, -1, -1)]
    return [(day, _resolve_day_path(day)) for day in days]


# ---------------------------------------------------------------------------
# Rainfall grid and mask
# ---------------------------------------------------------------------------

def _open_reference_raster(day_paths: Sequence[Tuple[dt.date, str | None]]):
    for _, path in reversed(day_paths):  # latest first
        if path is None:
            continue
        try:
            return rasterio.open(path)
        except Exception:
            continue
    raise FileNotFoundError("No readable rainfall raster found for the selected window")


def _build_mask(reference_ds: rasterio.io.DatasetReader) -> np.ndarray:
    county_shp = ROOT / "data/static/cb_2022_us_county_500k.shp"
    if not county_shp.exists():
        raise FileNotFoundError(f"county shapefile missing: {county_shp}")

    import geopandas as gpd

    gdf = gpd.read_file(county_shp)
    buncombe = gdf[gdf["GEOID"] == "37021"]
    if buncombe.empty:
        raise ValueError("Buncombe county polygon not found in shapefile")

    geom = buncombe.to_crs(reference_ds.crs).geometry.iloc[0]
    mask = features.rasterize(
        [(geom, 1)],
        out_shape=(reference_ds.height, reference_ds.width),
        transform=reference_ds.transform,
        fill=0,
        dtype="uint8",
    )
    return mask.astype(bool)


def _grid_centers(reference_ds: rasterio.io.DatasetReader, mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rows, cols = np.where(mask)
    xs, ys = reference_ds.transform * (cols + 0.5, rows + 0.5)
    return rows, cols, np.asarray(xs, dtype=np.float64), np.asarray(ys, dtype=np.float64)


def _sample_rainfall(
    day_paths: Sequence[Tuple[dt.date, str | None]],
    rows: np.ndarray,
    cols: np.ndarray,
    x_coords: np.ndarray,
    y_coords: np.ndarray,
    reference_ds: rasterio.io.DatasetReader,
) -> Dict[str, np.ndarray]:
    coord_cache: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    samples: List[np.ndarray] = []

    for day, path in day_paths:
        if path is None:
            samples.append(np.zeros_like(x_coords, dtype=np.float32))
            continue
        try:
            with rasterio.open(path) as ds:
                target_crs = ds.crs.to_string() if ds.crs else RAIN_FALLBACK_CRS
                if target_crs not in coord_cache:
                    xs, ys = warp_transform(reference_ds.crs, target_crs, x_coords, y_coords)
                    coord_cache[target_crs] = (
                        np.asarray(xs, dtype=np.float64),
                        np.asarray(ys, dtype=np.float64),
                    )
                xs, ys = coord_cache[target_crs]
                arr = np.array([val[0] if val.size else np.nan for val in ds.sample(zip(xs, ys))], dtype=np.float32)
                nodata = ds.nodata
                if nodata is not None:
                    arr = np.where(arr == nodata, np.nan, arr)
                samples.append(arr)
        except Exception:
            samples.append(np.zeros_like(x_coords, dtype=np.float32))

    stack = np.stack(samples, axis=0)
    rain_feats = _compute_rain_features(stack)
    return rain_feats


def _compute_rain_features(stack: np.ndarray) -> Dict[str, np.ndarray]:
    def _subset(n: int) -> np.ndarray:
        return stack[-n:] if stack.shape[0] >= n else stack

    def _sum_last(n: int) -> np.ndarray:
        with np.errstate(invalid="ignore"):
            return np.nansum(_subset(n), axis=0)

    def _max_last(n: int) -> np.ndarray:
        subset = _subset(n)
        with np.errstate(invalid="ignore"):
            out = np.nanmax(subset, axis=0)
        all_nan = np.isnan(subset).all(axis=0)
        out[all_nan] = np.nan
        return out

    return {
        "R1d": stack[-1],
        "R3d": _sum_last(3),
        "R7d": _sum_last(7),
        "R30d": _sum_last(30),
        "Max_Rainfall_3day": _max_last(3),
        "Max_Rainfall_30day": _max_last(30),
    }


# ---------------------------------------------------------------------------
# Static attribute sampling
# ---------------------------------------------------------------------------

def _load_static_frame() -> pd.DataFrame:
    df = pd.read_parquet(STATIC_PARQ)
    needed = {
        STATIC_COLS["x"],
        STATIC_COLS["y"],
        STATIC_COLS["elev"],
        STATIC_COLS["slope"],
        STATIC_COLS["soil"],
    }
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"Static parquet missing columns: {missing}")
    return df[list(needed)].copy()


def _build_static_index(static_df: pd.DataFrame) -> Dict[Tuple[float, float], Tuple[float, float, float]]:
    # For quick lookup by rounded x/y (meters). The rainfall grid is coarser, so rounding helps.
    index = {}
    for _, row in static_df.iterrows():
        key = (round(row[STATIC_COLS["x"]], 1), round(row[STATIC_COLS["y"]], 1))
        index[key] = (
            float(row[STATIC_COLS["elev"]]),
            float(row[STATIC_COLS["slope"]]),
            float(row[STATIC_COLS["soil"]]),
        )
    return index


def _sample_static_attributes(
    static_index: Dict[Tuple[float, float], Tuple[float, float, float]],
    x_coords: np.ndarray,
    y_coords: np.ndarray,
) -> Dict[str, np.ndarray]:
    elev = np.empty_like(x_coords, dtype=np.float32)
    slope = np.empty_like(x_coords, dtype=np.float32)
    soil = np.empty_like(x_coords, dtype=np.float32)

    default = (np.nan, np.nan, np.nan)
    for i, (x, y) in enumerate(zip(x_coords, y_coords)):
        key = (round(float(x), 1), round(float(y), 1))
        elev[i], slope[i], soil[i] = static_index.get(key, default)

    soil_flag = (soil >= 200).astype(np.int8)
    return {
        STATIC_COLS["elev"]: elev,
        STATIC_COLS["slope"]: slope,
        STATIC_COLS["soil"]: soil,
        "Soil_Depth_Deep200_Flag": soil_flag,
    }


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

def resolve_model_features() -> Tuple[Dict[str, object], Dict[str, List[str]], Dict[str, List[str]]]:
    models: Dict[str, object] = {}
    feature_lists: Dict[str, List[str]] = {}
    model_inputs: Dict[str, List[str]] = {}

    for key, spec in CFG["models"].items():
        raw_path = Path(spec["path"])
        if raw_path.is_absolute():
            path = raw_path
        else:
            path = ROOT / raw_path
            if not path.exists():
                path = MODELS_DIR / raw_path.name
        if not path.exists():
            raise FileNotFoundError(f"model missing: {path}")

        model = joblib.load(path)
        models[key] = model

        feats = list(spec["features"])
        input_names = [FEATURE_NAME_MAP.get(f, f) for f in feats]

        if hasattr(model, "named_steps"):
            for step in model.named_steps.values():
                if hasattr(step, "feature_names_in_"):
                    step.feature_names_in_ = np.array(input_names)
        elif hasattr(model, "feature_names_in_"):
            model.feature_names_in_ = np.array(input_names)

        feature_lists[key] = feats
        model_inputs[key] = input_names

    return models, feature_lists, model_inputs


# ---------------------------------------------------------------------------
# Prediction pipeline
# ---------------------------------------------------------------------------

def predict(
    models: Dict[str, object],
    feature_lists: Dict[str, List[str]],
    model_inputs: Dict[str, List[str]],
    day_paths: List[Tuple[dt.date, str | None]],
    target_date: str,
) -> int:
    reference_ds = _open_reference_raster(day_paths)
    mask = _build_mask(reference_ds)
    rows, cols, xs, ys = _grid_centers(reference_ds, mask)

    print(f"Sampling rainfall at {len(xs):,} PRISM grid cells…", flush=True)
    rain_feats = _sample_rainfall(day_paths, rows, cols, xs, ys, reference_ds)

    print("Sampling static attributes at grid centers…", flush=True)
    static_df = _load_static_frame()
    static_index = _build_static_index(static_df)
    static_attrs = _sample_static_attributes(static_index, xs, ys)

    print("Running models…", flush=True)
    results = pd.DataFrame({
        "row": rows.astype(np.int32),
        "col": cols.astype(np.int32),
        "x": xs,
        "y": ys,
    })
    for name in RAIN_FEATURES:
        results[name] = rain_feats[name]
    results[STATIC_COLS["elev"]] = static_attrs[STATIC_COLS["elev"]]
    results[STATIC_COLS["slope"]] = static_attrs[STATIC_COLS["slope"]]
    results[STATIC_COLS["soil"]] = static_attrs[STATIC_COLS["soil"]]
    results["Soil_Depth_Deep200_Flag"] = static_attrs["Soil_Depth_Deep200_Flag"]

    for model_key, model in models.items():
        feats = feature_lists[model_key]
        input_names = model_inputs[model_key]
        X_df = results[feats].copy()
        X_input = X_df.rename(columns=FEATURE_NAME_MAP)
        X_input = X_input[input_names]
        preds = (
            model.predict_proba(X_input)[:, 1]
            if hasattr(model, "predict_proba")
            else model.predict(X_input)
        )
        results[f"p_{model_key}"] = preds.astype(np.float32)

    out_dir = PRED_DIR / target_date
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"predictions_{target_date}.parquet"
    results.to_parquet(out_path, index=False)
    reference_ds.close()
    return len(results)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    default_date = dt.date.today() - dt.timedelta(days=1)
    target_str = sys.argv[1] if len(sys.argv) > 1 else default_date.strftime(DATE_FMT)
    target_date = dt.date.fromisoformat(target_str)

    models, feature_lists, model_inputs = resolve_model_features()
    day_paths = _collect_day_paths(target_date, RAIN_WINDOW_DAYS)
    rainfall_end = day_paths[-1][0]
    available = sum(1 for _, path in day_paths if path is not None)
    missing = len(day_paths) - available
    first_day = day_paths[0][0]
    print(
        f"Rainfall window: {first_day} → {rainfall_end} "
        f"({available} files, {missing} missing → zero-filled)."
    )

    count = predict(models, feature_lists, model_inputs, day_paths, target_str)

    meta = {
        "target_date": target_str,
        "rainfall_through": rainfall_end.strftime(DATE_FMT),
        "rows": count,
        "chunks": 1,
        "outputs": "parquet",
    }
    meta_path = PRED_DIR / target_str / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=2))
    print(
        f"ok: wrote {count:,} rows of predictions for {target_str} "
        f"(rainfall through {rainfall_end})"
    )


if __name__ == "__main__":
    main()
