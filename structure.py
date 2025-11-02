# scaffold.py
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

# Default project layout
DEFAULT_SPEC = {
    "files": ["main.py", ".gitignore", "README.md"],
    "dirs": {
        "data": {
            "dirs": {
                "rainfall data": {},
                "landslide data": {}
            }
        },
        "src": {},
        "tests": {}
    }
}

# Directories and files to ignore when printing tree
IGNORE_LIST = {
    ".git", "__pycache__", ".idea", "venv", "env", "lib", "Lib",
    ".DS_Store", ".pytest_cache", ".vscode", ".mypy_cache"
}

def build(struct: dict, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for f in struct.get("files", []):
        p = root / f
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.touch()
    for dname, dstruct in struct.get("dirs", {}).items():
        build(dstruct if isinstance(dstruct, dict) else {}, root / dname)

def render_tree(root: Path, prefix: str = "") -> str:
    if not root.exists():
        return ""
    entries = sorted(
        [e for e in root.iterdir() if e.name not in IGNORE_LIST and not e.name.startswith(".")],
        key=lambda p: (p.is_file(), p.name.lower())
    )
    lines = []
    for i, p in enumerate(entries):
        last = (i == len(entries) - 1)
        connector = "└── " if last else "├── "
        lines.append(f"{prefix}{connector}{p.name}")
        if p.is_dir():
            ext = "    " if last else "│   "
            lines.append(render_tree(p, prefix + ext))
    return "\n".join([ln for ln in lines if ln])

def parse_spec(args) -> dict:
    if args.spec:
        try:
            return json.loads(args.spec)
        except json.JSONDecodeError as e:
            sys.exit(f"Invalid JSON in --spec: {e}")
    if args.spec_file:
        p = Path(args.spec_file)
        if not p.exists():
            sys
