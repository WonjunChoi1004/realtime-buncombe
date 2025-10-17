import os, sys, glob, json, subprocess, datetime as dt
import numpy as np, rasterio as rio, joblib, yaml
from rasterio.enums import Resampling
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG  = yaml.safe_load((ROOT / "config.yaml").read_text())
P    = CFG["paths"]

MODEL_KEY = CFG["publish_model"]
FEATURES  = CFG["feature_order"]
MINZ, MAXZ = CFG["tiling"]["minzoom"], CFG["tiling"]["maxzoom"]

MODEL_PATHS = {
    "logistic": ROOT / P["model_dir"] / "logistic.joblib",
    "rf":       ROOT / P["model_dir"] / "rf.joblib",
    "xgb":      ROOT / P["model_dir"] / "xgb.joblib",
}
MODEL_BUNDLE = joblib.load(MODEL_PATHS[MODEL_KEY])
MODEL = MODEL_BUNDLE.get("model", MODEL_BUNDLE)

STATIC_DIR   = ROOT / P["data_static"]
RAIN_DIR     = ROOT / P["data_rain"]
PRED_DIR     = ROOT / P["predictions"]
WEB_TILES    = ROOT / P["web_tiles"]

TODAY = dt.date.today().isoformat()  # server local date
# If you publish for a specific date, allow override: python update_daily.py 2025-10-01
if len(sys.argv) > 1:
    TODAY = sys.argv[1]

def _open(path):
    return rio.open(path)

def _read_match(src_like, path):
    with _open(path) as r:
        if (r.transform == src_like.transform and
            r.width == src_like.width and r.height == src_like.height and
            r.crs == src_like.crs):
            return r.read(1)
        data = r.read(
            out_shape=(1, src_like.height, src_like.width),
            resampling=Resampling.bilinear
        )[0]
        return data

def _list_days(end_date, n_days, folder):
    end = dt.date.fromisoformat(end_date)
    days = [(end - dt.timedelta(days=i)).isoformat() for i in range(n_days-1, -1, -1)]
    paths = []
    for d in days:
        tif = Path(folder) / f"{d}.tif"
        if tif.exists():
            paths.append(str(tif))
    return paths

def build_rain_features(ref_ds, today):
    # Use: last 1, 3, 7, 30 days including today's forecast in data/rain/forecast/{today}.tif
    r1_paths  = _list_days(today, 1,  RAIN_DIR / "forecast") or _list_days(today, 1, RAIN_DIR)
    r3_paths  = _list_days(today, 3,  RAIN_DIR)
    r7_paths  = _list_days(today, 7,  RAIN_DIR)
    r30_paths = _list_days(today, 30, RAIN_DIR)

    def stack_sum(paths):
        if not paths: return np.zeros((ref_ds.height, ref_ds.width), dtype=np.float32)
        arr = None
        for p in paths:
            a = _read_match(ref_ds, p).astype(np.float32)
            arr = a if arr is None else (arr + a)
        return arr

    R1d  = stack_sum(r1_paths)
    R3d  = stack_sum(r3_paths)
    R7d  = stack_sum(r7_paths)
    R30d = stack_sum(r30_paths)
    return {"R1d":R1d, "R3d":R3d, "R7d":R7d, "R30d":R30d}

def load_static(ref_ds):
    slope = _read_match(ref_ds, STATIC_DIR / "slope_40m.tif").astype(np.float32)
    elev  = _read_match(ref_ds, STATIC_DIR / "elev_40m.tif").astype(np.float32)
    soil  = _read_match(ref_ds, STATIC_DIR / "soil_depth.tif").astype(np.float32)
    mask  = _read_match(ref_ds, STATIC_DIR / "buncombe_mask.tif").astype(np.uint8)
    return {"slope_40m":slope, "elev_40m":elev, "soil_depth":soil, "mask":mask}

def write_geotiff(ref_ds, arr, out_path, nodata=np.nan):
    profile = ref_ds.profile.copy()
    profile.update(count=1, dtype="float32", nodata=nodata, compress="lzw", tiled=True)
    with rio.open(out_path, "w", **profile) as w:
        w.write(arr.astype(np.float32), 1)

def gdal2tiles(src_tif, out_dir, minzoom=MINZ, maxzoom=MAXZ):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "gdal2tiles.py",
        "-r", CFG["tiling"]["resampling"],
        "-z", f"{minzoom}-{maxzoom}",
        "-w", "none",
        str(src_tif),
        str(out_dir)
    ]
    subprocess.check_call(cmd)

def main():
    # Use slope as reference grid
    with _open(STATIC_DIR / "slope_40m.tif") as ref:
        rain = build_rain_features(ref, TODAY)
        stat = load_static(ref)

        feats = []
        for name in FEATURES:
            if name in rain:
                feats.append(rain[name])
            else:
                feats.append(stat[name])
        stack = np.stack(feats, axis=-1)  # H x W x F
        H, W, F = stack.shape

        # Mask outside county
        mask = stat["mask"] == 1
        X = stack.reshape(-1, F)
        valid_idx = mask.reshape(-1)
        X_valid = X[valid_idx]

        yprob = np.zeros((H*W,), dtype=np.float32)
        if X_valid.size > 0:
            proba = MODEL.predict_proba(X_valid)[:, 1].astype(np.float32)
            yprob[valid_idx] = proba
        yprob = yprob.reshape(H, W)

        day_dir = PRED_DIR / TODAY
        day_dir.mkdir(parents=True, exist_ok=True)
        out_tif = day_dir / "prob.tif"
        write_geotiff(ref, yprob, out_tif)

        tiles_out = WEB_TILES / TODAY
        gdal2tiles(out_tif, tiles_out, MINZ, MAXZ)

        latest = WEB_TILES / "latest"
        if latest.exists() or latest.is_symlink():
            latest.unlink()
        latest.symlink_to(tiles_out.name)  # relative symlink

        meta = {
            "date": TODAY,
            "model": MODEL_KEY,
            "features": FEATURES,
            "minzoom": MINZ, "maxzoom": MAXZ
        }
        (day_dir / "meta.json").write_text(json.dumps(meta, indent=2))
        print(f"Published {TODAY}")

if __name__ == "__main__":
    main()
