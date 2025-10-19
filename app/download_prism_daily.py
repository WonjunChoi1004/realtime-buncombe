#!/usr/bin/env python3
# prism_sync_from_yaml.py
import datetime as dt
import json, sys, time, shutil, zipfile, re
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
import yaml

def load_config(cfg_path: Path):
    data = yaml.safe_load(cfg_path.read_text())
    ps = data.get("paths", {})
    psync = data.get("prism_sync", {})
    rain_dir = Path(psync.get("rainfall_dir") or ps.get("rainfall_dir", "data/rain"))
    if not rain_dir.is_absolute():
        rain_dir = cfg_path.parent / rain_dir

    return {
        "base_url": psync.get("base_url", "https://data.prism.oregonstate.edu/time_series/us/an/800m"),
        "variable": psync.get("variable", "ppt"),
        "timescale": psync.get("timescale", "daily"),
        "resolution": psync.get("resolution", "30s"),
        "rainfall_dir": rain_dir,
        "prefix": psync.get("prefix", "prism_ppt_us_30s_"),
        "start_offset_days": int(psync.get("start_offset_days", 1)),
        "end_offset_days": int(psync.get("end_offset_days", 30)),
        "retention_days": int(psync.get("retention_days", 30)),
        "compare_fields": list(psync.get("compare_fields", ["etag", "last_modified_utc", "content_length"])),
        "timeouts": {
            "head": int(psync.get("timeouts", {}).get("head_seconds", 30)),
            "get": int(psync.get("timeouts", {}).get("get_seconds", 180)),
        },
        "retries": {
            "max": int(psync.get("retries", {}).get("max_attempts", 3)),
            "backoff": int(psync.get("retries", {}).get("backoff_seconds", 2)),
        },
        "extract": bool(psync.get("extract", True)),
        "delete_zip_after_extract": bool(psync.get("delete_zip_after_extract", True)),
        "verify_tif": bool(psync.get("verify_tif", True)),
    }

def ymd(d): return d.strftime("%Y%m%d")

def build_url(cfg, d: dt.date) -> str:
    return f"{cfg['base_url']}/{cfg['variable']}/{cfg['timescale']}/{d.year}/{cfg['prefix']}{ymd(d)}.zip"

def zip_path(cfg, d): return cfg["rainfall_dir"] / f"{cfg['prefix']}{ymd(d)}.zip"
def meta_path(cfg, d): return cfg["rainfall_dir"] / f"{cfg['prefix']}{ymd(d)}.meta.json"
def folder_path(cfg, d): return cfg["rainfall_dir"] / f"{cfg['prefix']}{ymd(d)}"
def tif_path(cfg, d): return folder_path(cfg, d) / f"{cfg['prefix']}{ymd(d)}.tif"

def head_remote(cfg, d):
    url = build_url(cfg, d)
    r = requests.head(url, allow_redirects=True, timeout=cfg["timeouts"]["head"])
    if r.status_code == 404: return None
    r.raise_for_status()
    lm = r.headers.get("Last-Modified")
    etag = r.headers.get("ETag")
    cl = r.headers.get("Content-Length")
    lm_iso = parsedate_to_datetime(lm).astimezone(dt.timezone.utc).isoformat() if lm else None
    size = int(cl) if cl and cl.isdigit() else None
    return {"last_modified_utc": lm_iso, "etag": etag, "content_length": size}

def load_meta(mpath: Path):
    if mpath.exists():
        try: return json.loads(mpath.read_text())
        except: return {}
    return {}

def save_meta(mpath: Path, meta: dict):
    mpath.write_text(json.dumps(meta, indent=2, sort_keys=True))

def needs_update_by_meta(local_meta: dict, remote_meta: dict, fields: list) -> bool:
    if not remote_meta: return False
    if not local_meta: return True
    for f in fields:
        if remote_meta.get(f) != local_meta.get(f):
            return True
    return False

def retry_get(url: str, timeout: int, retries: int, backoff: int):
    for i in range(retries):
        try:
            return requests.get(url, stream=True, timeout=timeout)
        except Exception as e:
            if i == retries - 1: raise
            time.sleep(backoff * (i + 1))

def download_zip(cfg, d):
    url = build_url(cfg, d)
    zpath = zip_path(cfg, d)
    zpath.parent.mkdir(parents=True, exist_ok=True)
    print(f"[GET ] {d} → {url}")
    r = retry_get(url, cfg["timeouts"]["get"], cfg["retries"]["max"], cfg["retries"]["backoff"])
    r.raise_for_status()
    tmp = zpath.with_suffix(".zip.tmp")
    with tmp.open("wb") as f:
        for chunk in r.iter_content(1 << 20):
            if chunk: f.write(chunk)
    tmp.replace(zpath)
    return zpath

def expand_zip(cfg, zpath: Path, d):
    fldr = folder_path(cfg, d)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(fldr)
    print(f"[UNZIP] Extracted → {fldr}")

def sync_day(cfg, d):
    z = zip_path(cfg, d)
    m = meta_path(cfg, d)

    remote = head_remote(cfg, d)
    if not remote:
        print(f"[SKIP] {d} not found online.")
        return

    local_meta = load_meta(m)
    update_needed = needs_update_by_meta(local_meta, remote, cfg["compare_fields"])

    if update_needed:
        if z.exists(): z.unlink()
        if m.exists(): m.unlink()
        if folder_path(cfg, d).exists():
            shutil.rmtree(folder_path(cfg, d))
            print(f"[CLEAN] {d} removed old expanded folder → {folder_path(cfg, d).name}")
        z = download_zip(cfg, d)
        save_meta(m, {
            "last_modified_utc": remote.get("last_modified_utc"),
            "etag": remote.get("etag"),
            "content_length": remote.get("content_length"),
            "synced_utc": dt.datetime.now(dt.timezone.utc).isoformat()
        })
        print(f"[DONE] Updated ZIP for {d}")
    else:
        print(f"[OK  ] {d} metadata matches remote")

    if cfg["extract"]:
        if not tif_path(cfg, d).exists():
            print(f"[MISS] {d} missing expanded .tif — extracting now.")
            if not z.exists():
                z = download_zip(cfg, d)
                save_meta(m, {
                    "last_modified_utc": remote.get("last_modified_utc"),
                    "etag": remote.get("etag"),
                    "content_length": remote.get("content_length"),
                    "synced_utc": dt.datetime.now(dt.timezone.utc).isoformat()
                })
            expand_zip(cfg, z, d)
            if cfg["verify_tif"] and not tif_path(cfg, d).exists():
                print(f"[ERR ] {d} extraction failed — .tif not found.")
            elif cfg["delete_zip_after_extract"] and z.exists():
                z.unlink()
                print(f"[CLEAN] {d} removed ZIP after extraction.")
        else:
            if cfg["delete_zip_after_extract"] and z.exists() and not update_needed:
                z.unlink()
                print(f"[CLEAN] {d} removed ZIP (expanded present, metadata match).")
            else:
                print(f"[OK  ] {d} expanded data present ({tif_path(cfg, d).name})")

def cleanup_old_data(cfg, keep_dates: set):
    PREFIX = cfg["prefix"]
    name_re = re.compile(rf"^{re.escape(PREFIX)}(\d{{8}})$")
    file_re = re.compile(rf"^{re.escape(PREFIX)}(\d{{8}})\.(zip|meta\.json)$")
    root = cfg["rainfall_dir"]
    if not root.exists(): return
    for p in root.iterdir():
        d = None
        m = name_re.match(p.name)
        if m:
            try: d = dt.datetime.strptime(m.group(1), "%Y%m%d").date()
            except: pass
        else:
            m2 = file_re.match(p.name)
            if m2:
                try: d = dt.datetime.strptime(m2.group(1), "%Y%m%d").date()
                except: pass
        if d and d not in keep_dates:
            try:
                if p.is_dir():
                    shutil.rmtree(p)
                    print(f"[PRUNE] Removed old folder → {p.name}")
                else:
                    p.unlink()
                    print(f"[PRUNE] Removed old file → {p.name}")
            except Exception as e:
                print(f"[ERR  ] Failed to remove {p.name}: {e}")

def main():
    # 🔹 Default config path changed here (now points to project root)
    cfg_path = Path("/Users/wonjunchoi/PycharmProjects/realtime-buncombe/config.yaml")
    cfg = load_config(cfg_path)

    today = dt.date.today()
    start = cfg["start_offset_days"]
    end = cfg["end_offset_days"]
    keep_window = cfg["retention_days"]

    for delta in range(start, end + 1):
        d = today - dt.timedelta(days=delta)
        try:
            sync_day(cfg, d)
        except Exception as e:
            print(f"[ERR ] {d} {e}")

    keep = { today - dt.timedelta(days=delta) for delta in range(1, keep_window + 1) }
    print("[INFO] Pruning files outside the past window...")
    cleanup_old_data(cfg, keep)

if __name__ == "__main__":
    main()
