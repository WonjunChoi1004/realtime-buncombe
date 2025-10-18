import pandas as pd
from pathlib import Path
from shapely.geometry import Point
import geopandas as gpd
from app.utils import load_cfg, log

# Reads your combined parquet and standardizes columns:
# adds cell_id if missing, adds geometry_wkt if missing, saves static_grid.parquet.

def main():
    cfg = load_cfg()
    L = log("prep")
    p_src = cfg["paths"]["src_static_parquet"]
    p_out = cfg["paths"]["static_grid"]
    cols = cfg["columns"]
    epsg = cfg["crs"]["static_epsg"]

    df = pd.read_parquet(p_src)
    # rename if needed (no-op if already matches)
    rename_map = {}
    for k in ("elev","slope","soil","x","y","row","col","wkt","cell_id"):
        if k in cols and cols[k] in df.columns:
            rename_map[cols[k]] = cols[k]
    df = df.rename(columns=rename_map)

    # ensure required static columns exist
    need_any_xy = ("X" in df.columns and "Y" in df.columns)
    need_any_rc = ("row" in df.columns and "col" in df.columns)

    if "cell_id" not in df.columns:
        if need_any_rc:
            df["cell_id"] = (df["row"].astype("int64")<<21) + df["col"].astype("int64")
        else:
            df["cell_id"] = df.reset_index().index

    if "geometry_wkt" not in df.columns:
        if need_any_xy:
            g = gpd.GeoDataFrame(df.copy(), geometry=[Point(xy) for xy in zip(df["X"], df["Y"])], crs=epsg)
            df["geometry_wkt"] = g.geometry.to_wkt()
            df = df.drop(columns=["geometry"])
        else:
            raise ValueError("Need either geometry_wkt or X/Y to build geometry_wkt.")

    keep = ["cell_id","geometry_wkt","elev_40m","slope_40m","soil_depth_cm"]
    for c in keep:
        if c not in df.columns:
            raise ValueError(f"Missing required column in static parquet: {c}")

    Path(p_out).parent.mkdir(parents=True, exist_ok=True)
    df[keep].to_parquet(p_out, index=False)
    L.info(f"static_grid.parquet saved → {p_out} rows={len(df)}")

if __name__ == "__main__":
    main()
