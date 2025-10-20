#!/usr/bin/env python3
import os, datetime, subprocess, sys
from pathlib import Path

REPO = Path("/Users/wonjunchoi/PycharmProjects/realtime-buncombe")
LOG_DIR = REPO / "logs"
LAST_RUN = LOG_DIR / "last_run.txt"
PYTHON = REPO / "venv/bin/python"
AUTO_SCRIPT = REPO / "app/auto_update.py"

def already_ran_today():
    if not LAST_RUN.exists():
        return False
    today = datetime.date.today()
    try:
        t = datetime.datetime.fromtimestamp(LAST_RUN.stat().st_mtime).date()
        return t == today
    except Exception:
        return False

def run_pipeline():
    cmd = [
        str(PYTHON),
        str(AUTO_SCRIPT)
    ]
    subprocess.run(cmd, cwd=str(REPO))
    LAST_RUN.touch()

def main():
    LOG_DIR.mkdir(exist_ok=True)
    if already_ran_today():
        print("✅ Already ran today, skipping.")
        return
    print("▶️ Running daily auto-update job...")
    run_pipeline()

if __name__ == "__main__":
    main()
