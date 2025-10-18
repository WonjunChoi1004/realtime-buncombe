import os, glob, yaml, logging
from datetime import datetime
import pandas as pd
import geopandas as gpd
from shapely import wkt

def load_cfg(path="config.yaml"):
    with open(path,"r") as f:
        return yaml.safe_load(f)

def log(name="rt"):
    lg = logging.getLogger(name)
    if not lg.handlers:
        lg.setLevel(logging.INFO)
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        lg.addHandler(h)
    return lg

def ensure_dirs(cfg):
    for k in ("rainfall_dir","predictions_dir","models_dir"):
        os.makedirs(cfg["paths"][k], exist_ok=True)

def latest_parquet(dir_path):
    files = sorted(glob.glob(os.path.join(dir_path, "*.parquet")))
    if not files: raise FileNotFoundError(f"No parquet in {dir_path}")
    return files[-1]

def df_to_gdf(df, wkt_col, epsg):
    g = df.copy()
    g["geometry"] = g[wkt_col].apply(wkt.loads)
    return gpd.GeoDataFrame(g.drop(columns=[wkt_col]), geometry="geometry", crs=epsg)

def today():
    return datetime.now().strftime("%Y-%m-%d")

def require_cols(df, cols):
    missing = [c for c in cols if c not in df.columns]
    if missing: raise ValueError(f"Missing columns: {missing}")
