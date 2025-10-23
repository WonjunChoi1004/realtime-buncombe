#!/usr/bin/env python3
import subprocess, sys, os, logging, time, socket
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = REPO_ROOT / "app"
PYTHON = os.environ.get("RB_PYTHON", sys.executable)
GIT_REMOTE = os.environ.get("RB_GIT_REMOTE", "origin")
GIT_BRANCH = os.environ.get("RB_GIT_BRANCH", "main")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("auto")

def run(cmd, cwd=None):
    p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if p.stdout:
        log.info(p.stdout.rstrip())
    if p.returncode != 0:
        raise SystemExit(f"Command failed ({p.returncode}): {' '.join(cmd)}")

def internet_available(host="8.8.8.8", port=53, timeout=3):
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except OSError:
        return False

def wait_for_internet():
    while not internet_available():
        log.warning("No internet connection — delaying run. Retrying in 15 minutes...")
        time.sleep(900)  # 15 minutes
    log.info("Internet connection detected. Proceeding with update.")

def git_has_changes():
    p = subprocess.run(["git", "status", "--porcelain"], cwd=REPO_ROOT, stdout=subprocess.PIPE, text=True)
    return p.stdout.strip() != ""

def git_commit_and_push():
    if not git_has_changes():
        log.info("No changes to commit.")
        return
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run(["git", "add", "-A"], cwd=REPO_ROOT)
    run(["git", "commit", "-m", f"Auto-update: rainfall & predictions @ {ts}"], cwd=REPO_ROOT)
    for i in range(3):
        try:
            run(["git", "push", GIT_REMOTE, GIT_BRANCH], cwd=REPO_ROOT)
            log.info("Push succeeded.")
            return
        except SystemExit as e:
            log.warning(f"Push failed (attempt {i+1}/3): {e}")
            if not internet_available():
                log.warning("Internet lost mid-push — waiting to retry connection.")
                wait_for_internet()
            time.sleep(5 * (i + 1))
    raise SystemExit("Push failed after 3 attempts.")

def main():
    wait_for_internet()  # ✅ new: ensure online before running

    log.info("Running download_prism_daily.py")
    run([PYTHON, str(APP_DIR / "download_prism_daily.py")], cwd=APP_DIR)

    log.info("Running predict_daily_triple.py")
    run([PYTHON, str(APP_DIR / "predict_daily_triple.py")], cwd=APP_DIR)

    log.info("Committing and pushing changes")
    git_commit_and_push()

if __name__ == "__main__":
    main()
