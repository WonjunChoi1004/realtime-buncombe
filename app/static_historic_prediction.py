#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import subprocess
import importlib
import importlib.util
from pathlib import Path
from typing import Iterable, List, Tuple, Optional

import numpy as np
import predict_daily_triple as pdt

ROOT: Path = pdt.ROOT
PRED_DIR: Path = pdt.PRED_DIR
DATE_FMT: str = pdt.DATE_FMT
RAIN_WINDOW_DAYS: int = pdt.RAIN_WINDOW_DAYS

# Optional: if your downloader accepts a --base-url flag, this will be used.
PRISM_BASE_URL: str = "https://data.prism.oregonstate.edu/time_series/us/an/800m"

def _daterange(start: dt.date, end: dt.date) -> Iterable[dt.date]:
    for i in range((end - start).days + 1):
        yield start + dt.timedelta(days=i)

def _out_paths(date_str: str) -> tuple[Path, Path, Path, Path]:
    out_dir = pdt._ym_dir(date_str)  # predictions/historicData/YYYY/MM/
    return (
        out_dir,
        out_dir / f"predictions_{date_str}.parquet",
        out_dir / f"map_{date_str}.geojson",
        out_dir / f"meta_{date_str}.json",
    )

def _exists_all(date_str: str) -> bool:
    _, pq, gj, meta = _out_paths(date_str)
    return pq.exists() and gj.exists() and meta.exists()

def _write_meta(date_str: str, rainfall_end: dt.date, models: list[str]) -> Path:
    out_dir, pq, gj, meta = _out_paths(date_str)
    meta_obj = {
        "date": date_str,
        "rainfall_through": rainfall_end.strftime(DATE_FMT),
        "outputs": {
            "parquet": str(pq.relative_to(ROOT)),
            "geojson": str(gj.relative_to(ROOT)),
            "meta": str(meta.relative_to(ROOT)),
        },
        "models": models,
        "pipeline": "historic_period",
    }
    meta.write_text(json.dumps(meta_obj, indent=2))
    return meta

def _update_index_runs_only(date_str: str, parquet: Path, geojson: Path, meta: Path) -> None:
    idx_path = PRED_DIR / "index.json"
    if idx_path.exists():
        try:
            manifest = json.loads(idx_path.read_text())
        except Exception:
            manifest = {}
    else:
        manifest = {}

    runs = manifest.get("runs", [])
    rel_parquet = str(parquet.relative_to(ROOT))
    rel_geojson = str(geojson.relative_to(ROOT))
    rel_meta = str(meta.relative_to(ROOT))

    replaced = False
    for r in runs:
        if r.get("date") == date_str:
            r.update({"geojson": rel_geojson, "parquet": rel_parquet, "meta": rel_meta})
            replaced = True
            break
    if not replaced:
        runs.append({"date": date_str, "geojson": rel_geojson, "parquet": rel_parquet, "meta": rel_meta})

    runs = sorted(runs, key=lambda x: x.get("date", ""), reverse=True)
    manifest["runs"] = runs

    # Do NOT modify manifest["latest"] or write latest.* files.
    idx_path.write_text(json.dumps(manifest, indent=2))

def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Backfill historic daily predictions into historicData and index.json (runs only). Also auto-downloads requisite PRISM rainfall.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--start", help="YYYY-MM-DD inclusive")
    ap.add_argument("--end", help="YYYY-MM-DD inclusive (required with --start)")
    g.add_argument("--dates", help="Comma-separated YYYY-MM-DD list")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--force", action="store_true")
    # If your downloader needs a yaml config, you can pipe it via env or args; left minimal here.
    return ap.parse_args()

def _build_days(args: argparse.Namespace) -> List[dt.date]:
    if args.dates:
        return [dt.date.fromisoformat(s.strip()) for s in args.dates.split(",") if s.strip()]
    if not args.end:
        raise ValueError("--end required when using --start")
    start = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end)
    if end < start:
        raise ValueError("end < start")
    return list(_daterange(start, end))

# -------- PRISM auto-download integration --------

def _find_missing_dates_for_windows(days: List[dt.date]) -> List[dt.date]:
    missing: set[dt.date] = set()
    for d in days:
        day_paths: List[Tuple[dt.date, str | None]] = pdt._collect_day_paths(d, RAIN_WINDOW_DAYS)
        for date_i, path_i in day_paths:
            if path_i is None:
                missing.add(date_i)
    return sorted(missing)

def _coalesce_into_ranges(dates: List[dt.date]) -> List[Tuple[dt.date, dt.date]]:
    if not dates:
        return []
    dates_sorted = sorted(dates)
    ranges: List[Tuple[dt.date, dt.date]] = []
    start = prev = dates_sorted[0]
    for cur in dates_sorted[1:]:
        if (cur - prev).days == 1:
            prev = cur
            continue
        ranges.append((start, prev))
        start = prev = cur
    ranges.append((start, prev))
    return ranges

def _import_downloader_module() -> Optional[object]:
    # Try to import a sibling module named download_prism_daily
    try:
        return importlib.import_module("download_prism_daily")
    except Exception:
        # Try app.download_prism_daily if your project uses app/
        try:
            return importlib.import_module("app.download_prism_daily")
        except Exception:
            return None

def _downloader_script_path() -> Optional[Path]:
    # Locate the script file to run via subprocess if no callable function exists
    for mod_name in ("download_prism_daily", "app.download_prism_daily"):
        spec = importlib.util.find_spec(mod_name)
        if spec and spec.origin and spec.origin.endswith(".py"):
            return Path(spec.origin)
    # Fallback: relative to this script (common layout)
    cand1 = (Path(__file__).resolve().parent / "download_prism_daily.py")
    if cand1.exists():
        return cand1
    cand2 = (ROOT / "app" / "download_prism_daily.py")
    if cand2.exists():
        return cand2
    return None

def _call_downloader_func(mod: object, start: dt.date, end: dt.date) -> bool:
    """
    Try common function names in your downloader:
      - download_range(start_date, end_date, base_url=None)
      - ensure_range(start_date, end_date, base_url=None)
      - main(args_namespace_like)
    Returns True if it looked like it ran successfully.
    """
    for fname in ("download_range", "ensure_range"):
        fn = getattr(mod, fname, None)
        if callable(fn):
            try:
                # Prefer signature with base_url if available
                try:
                    fn(start, end, base_url=PRISM_BASE_URL)
                except TypeError:
                    fn(start, end)
                return True
            except Exception as e:
                print(f"  downloader.{fname} failed: {e!r}")
                return False

    # Try a CLI-style entry if module exposes main for argparse
    main_fn = getattr(mod, "main", None)
    if callable(main_fn):
        try:
            # Construct a dummy argparse-like namespace if needed;
            # many CLIs accept sys.argv, so this might not work directly.
            # We'll prefer subprocess below; keep this as last resort.
            print("  downloader.main() detected, skipping direct call; will use subprocess instead.")
        except Exception:
            pass
    return False

def _call_downloader_subprocess(script: Path, start: dt.date, end: dt.date) -> bool:
    cmd = [sys.executable, str(script), "--start", start.isoformat(), "--end", end.isoformat()]
    # Try passing base URL if the script supports it; harmless if ignored.
    cmd += ["--base-url", PRISM_BASE_URL]
    print(f"  subprocess: {' '.join(cmd)}")
    try:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"  downloader subprocess nonzero exit ({proc.returncode})")
            if proc.stdout:
                print(proc.stdout.strip())
            if proc.stderr:
                print(proc.stderr.strip())
            return False
        return True
    except Exception as e:
        print(f"  downloader subprocess failed: {e!r}")
        return False

def _ensure_prism_data_for_ranges(ranges: List[Tuple[dt.date, dt.date]]) -> None:
    if not ranges:
        return
    mod = _import_downloader_module()
    script = _downloader_script_path()

    for s, e in ranges:
        print(f"[download] Ensuring PRISM daily rainfall {s} → {e}")
        ok = False
        if mod:
            ok = _call_downloader_func(mod, s, e)
        if not ok and script:
            ok = _call_downloader_subprocess(script, s, e)
        if not ok:
            print(f"  WARN: Could not auto-download {s} → {e}. Proceeding; missing days will be treated as zero if your pipeline allows.")

# -------------------------------------------------

def main():
    args = _parse_args()
    days = _build_days(args)

    # Identify all missing rainfall dates across all windows and fetch them once.
    print("Scanning required rainfall windows…")
    missing_dates = _find_missing_dates_for_windows(days)
    if missing_dates:
        print(f"  missing daily grids: {len(missing_dates)} day(s)")
        date_ranges = _coalesce_into_ranges(missing_dates)
        _ensure_prism_data_for_ranges(date_ranges)
    else:
        print("  all required rainfall files already present.")

    models, feature_lists, model_inputs = pdt.resolve_model_features()
    model_names = list(models.keys())

    ok, skipped, failed = [], [], []

    for d in days:
        ds = d.strftime(DATE_FMT)

        if args.skip_existing and _exists_all(ds):
            print(f"[{ds}] skip (exists)")
            skipped.append(ds)
            continue

        try:
            day_paths: List[Tuple[dt.date, str | None]] = pdt._collect_day_paths(d, RAIN_WINDOW_DAYS)
            rainfall_end = day_paths[-1][0]
            have = sum(1 for _, p in day_paths if p is not None)
            miss = len(day_paths) - have
            print(f"[{ds}] window {day_paths[0][0]} → {rainfall_end} ({have} ok, {miss} missing→zero)")

            count, results, src_crs = pdt.predict(models, feature_lists, model_inputs, day_paths, ds)

            out_dir, pq, gj, meta = _out_paths(ds)
            pdt._save_geojson(results, results["x"].to_numpy(), results["y"].to_numpy(), src_crs, gj, ds)
            meta = _write_meta(ds, rainfall_end, model_names)

            _update_index_runs_only(ds, pq, gj, meta)
            print(f"[{ds}] ok — {count:,} rows → {out_dir}")
            ok.append(ds)

        except Exception as e:
            print(f"[{ds}] FAIL — {e}")
            failed.append((ds, repr(e)))

    print("\nSummary")
    print(f"  total: {len(days)}")
    print(f"  ok: {len(ok)}")
    print(f"  skipped: {len(skipped)}")
    print(f"  failed: {len(failed)}")
    if failed:
        for ds, err in failed:
            print(f"    {ds}: {err}")

if __name__ == "__main__":
    main()
