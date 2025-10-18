"""Compute rainfall feature averages for Buncombe County and render maps."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

try:
    from .rainfall_features import (
        CFG,
        ROOT,
        RAIN_DIR,
        FEATURE_COLUMNS,
        available_dates,
        compute_feature_arrays,
    )
except ImportError:  # Allow running as a script
    from rainfall_features import (  # type: ignore
        CFG,
        ROOT,
        RAIN_DIR,
        FEATURE_COLUMNS,
        available_dates,
        compute_feature_arrays,
    )


def describe(features: dict[str, np.ndarray], mask: np.ndarray) -> None:
    area_pixels = mask.sum()
    print(f"Pixels within Buncombe mask: {area_pixels}")
    for name in FEATURE_COLUMNS:
        data = np.where(mask, features[name], np.nan)
        mean_val = np.nanmean(data)
        print(f"{name:<20} mean = {mean_val:8.3f} mm")


def render_map(
    features: dict[str, np.ndarray], meta: dict, mask: np.ndarray, out_path: Path
) -> Path:
    """Save a six-panel map of rainfall features limited to Buncombe County."""

    rows, cols = np.where(mask)
    if rows.size == 0:
        raise ValueError("Mask is empty; cannot render map")

    rmin, rmax = rows.min(), rows.max()
    cmin, cmax = cols.min(), cols.max()

    transform = meta["transform"]
    left = transform.c + cmin * transform.a
    top = transform.f + rmin * transform.e
    right = transform.c + (cmax + 1) * transform.a
    bottom = transform.f + (rmax + 1) * transform.e
    extent = (left, right, bottom, top)

    fig, axes = plt.subplots(2, 3, figsize=(12, 8), constrained_layout=True)
    for ax, name in zip(axes.flat, FEATURE_COLUMNS):
        arr_full = np.where(mask, features[name], np.nan)
        arr = arr_full[rmin : rmax + 1, cmin : cmax + 1]
        im = ax.imshow(arr, cmap="viridis", extent=extent, origin="upper")
        ax.set_title(name)
        ax.set_xlabel("Easting (m)")
        ax.set_ylabel("Northing (m)")
        fig.colorbar(im, ax=ax, shrink=0.7)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200)
    plt.close(fig)
    return out_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Average rainfall features for Buncombe County and render diagnostic maps"
    )
    parser.add_argument("--date", type=str, help="Target date (YYYY-MM-DD). Defaults to latest available")
    parser.add_argument("--window", type=int, default=30, help="Trailing window size (days)")
    parser.add_argument(
        "--save",
        type=Path,
        help="Optional output PNG path for the feature map",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dates = available_dates()
    if not dates:
        raise SystemExit(f"No rainfall rasters found in {RAIN_DIR}")

    target = dt.date.fromisoformat(args.date) if args.date else dates[-1]
    arrays, mask, meta, resolved = compute_feature_arrays(target, args.window)
    features = arrays

    print(
        f"Requested target: {target} | using rainfall through {resolved} (window={args.window} days)"
    )
    describe(features, mask)

    out_path = args.save
    if out_path is None:
        pred_dir = ROOT / CFG["paths"]["predictions_dir"]
        out_path = pred_dir / f"rainfall_features_{target.isoformat()}.png"

    saved = render_map(features, meta, mask, out_path)
    print(f"Map saved to: {saved}")


if __name__ == "__main__":
    main()
