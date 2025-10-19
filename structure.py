# structure.py
# Validate repo layout and render an interactive structure map.

import argparse, os, re, json, sys, hashlib, fnmatch
from pathlib import Path
from datetime import datetime
from typing import Optional

# === DEFAULTS ===
DEFAULT_ROOT = Path("/Users/wonjunchoi/PycharmProjects/realtime-buncombe").resolve()
DEFAULT_IGNORE = {
    ".git", ".hg", ".svn", ".DS_Store", "__pycache__", ".ipynb_checkpoints",
    "node_modules", "dist", "build", ".venv", "venv", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", ".parcel-cache", ".gradle", ".next",
    ".cache", ".idea", ".vscode"
}
CODE_EXT = {".py", ".ipynb", ".js", ".ts", ".java", ".cpp", ".c", ".cs", ".rb"}
DATA_EXT = {".csv", ".tsv", ".parquet", ".json", ".yaml", ".yml", ".xml", ".xlsx", ".xls", ".geojson", ".shp", ".tif", ".tiff"}
DOC_EXT  = {".md", ".txt", ".pdf", ".docx", ".pptx", ".html"}
MODEL_EXT= {".pkl", ".joblib", ".onnx", ".pt", ".h5"}
WEB_EXT  = {".html", ".css", ".js"}

# Built-in rules (override via --rules)
DEFAULT_RULES = {
    "must_exist_dirs": [
        "app", "data", "data/static", "data/rain", "models", "predictions"
    ],
    "must_exist_files": [
        "README.md", "predictions/latest.geojson"
    ],
    "scripts_present_anywhere": [
        "download_prism_daily.py", "rainfall_features.py", "predict_daily_triple.py"
    ],
    "config_file": "config.yaml",
    "gitignore_required": True,
    "warn_duplicate_basenames": True,
    "size_limits_mb": [  # glob per-file limits
        {"glob": "**/*.py", "max_mb": 1},
        {"glob": "data/static/**/*", "max_mb": 2048}
    ],
    "large_data_threshold_mb": 100,  # flag large non-allowed data files
    "large_data_allowed_ext": [".parquet", ".geojson", ".tif", ".tiff", ".csv"]
}

# === HTML TEMPLATE ===
HTML_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8"><title>Project Map</title>
<style>
body { font-family: system-ui, sans-serif; margin:0; }
#net { width:100vw; height:100vh; }
</style>
<script src="https://unpkg.com/vis-network@9.1.6/standalone/umd/vis-network.min.js"></script>
</head>
<body>
<div id="net"></div>
<script>
const DATA = __DATA__;
const groups = {
  "dir":   { color:{background:"#fde68a"} },
  "code":  { color:{background:"#bfdbfe"} },
  "data":  { color:{background:"#ffd6a5"} },
  "model": { color:{background:"#e9d5ff"} },
  "doc":   { color:{background:"#fecaca"} },
  "web":   { color:{background:"#c7f9cc"} },
  "other": { color:{background:"#e5e7eb"} }
};
const nodes = new vis.DataSet(DATA.nodes);
const edges = new vis.DataSet(DATA.edges);
new vis.Network(document.getElementById('net'), {nodes,edges}, {
  physics:{ stabilization:true },
  groups
});
</script>
</body>
</html>
"""

# === Helpers ===
def classify(path: Path):
    if path.is_dir(): return "dir"
    ext = path.suffix.lower()
    if ext in CODE_EXT: return "code"
    if ext in DATA_EXT: return "data"
    if ext in MODEL_EXT: return "model"
    if ext in WEB_EXT: return "web"
    if ext in DOC_EXT: return "doc"
    return "other"

def rel_to(root: Path, p: Path):
    try: return str(p.relative_to(root))
    except Exception: return str(p)

def should_skip(path: Path, ignore_names: set):
    return any(part in ignore_names for part in path.parts)

def walk_files(root: Path, ignore_names: set):
    for dirpath, dirnames, filenames in os.walk(root):
        dpath = Path(dirpath)
        # prune ignored dirs
        dirnames[:] = [d for d in dirnames if not should_skip(dpath/ d, ignore_names)]
        for fn in filenames:
            if fn.startswith("."):  # hidden files skipped from map, but still eligible for checks when needed
                pass
            yield dpath / fn

# === Graph ===
def build_graph(root: Path, ignore_names):
    nodes, edges, seen = [], [], set()

    def add_node(pid, label, group):
        if pid not in seen:
            seen.add(pid)
            nodes.append({"id": pid, "label": label, "group": group, "shape": "box"})

    def add_edge(a, b):
        edges.append({"from": a, "to": b, "arrows": "to"})

    add_node("root", root.name, "dir")

    for dirpath, dirnames, filenames in os.walk(root):
        dpath = Path(dirpath)
        if should_skip(dpath, ignore_names): continue
        did = f"dir:{rel_to(root, dpath)}" if dpath != root else "root"
        add_node(did, dpath.name + "/", "dir")
        for dn in dirnames:
            cpath = dpath / dn
            if should_skip(cpath, ignore_names): continue
            cid = f"dir:{rel_to(root, cpath)}"
            add_node(cid, dn + "/", "dir")
            add_edge(did, cid)
        for fn in filenames:
            if fn.startswith("."): continue
            fpath = dpath / fn
            if should_skip(fpath, ignore_names): continue
            fid = f"file:{rel_to(root, fpath)}"
            grp = classify(fpath)
            add_node(fid, fn, grp)
            add_edge(did, fid)
    return {"nodes": nodes, "edges": edges, "meta": {"root": str(root)}}

def write_html(graph: dict, out_path: Path):
    html = HTML_TEMPLATE.replace("__DATA__", json.dumps(graph, separators=(",", ":")))
    out_path.write_text(html, encoding="utf-8")

# === Rule loading ===
def load_rules(path: Optional[str]):
    if not path: return DEFAULT_RULES
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"rules file not found: {p}")
    if p.suffix.lower() in {".yml", ".yaml"}:
        try:
            import yaml  # optional
        except Exception as e:
            raise RuntimeError("PyYAML required to read YAML rules") from e
        with p.open("r", encoding="utf-8") as f:
            user_rules = yaml.safe_load(f) or {}
    else:
        with p.open("r", encoding="utf-8") as f:
            user_rules = json.load(f)
    # shallow merge
    merged = dict(DEFAULT_RULES)
    merged.update(user_rules or {})
    return merged

# === Checks ===
def check_must_exist(root: Path, rules, report):
    for d in rules.get("must_exist_dirs", []):
        p = root / d
        ok = p.is_dir()
        report.append(("FAIL" if not ok else "PASS", f"dir:{d}", "exists" if ok else "missing"))
    for f in rules.get("must_exist_files", []):
        p = root / f
        ok = p.is_file()
        report.append(("FAIL" if not ok else "PASS", f"file:{f}", "exists" if ok else "missing"))

def check_scripts_anywhere(root: Path, rules, report, ignore):
    targets = set(rules.get("scripts_present_anywhere", []))
    found = {t: False for t in targets}
    for fp in walk_files(root, ignore):
        if fp.name in targets:
            found[fp.name] = True
    for name, ok in found.items():
        report.append(("FAIL" if not ok else "PASS", f"script:{name}", "found" if ok else "not found"))

def check_config(root: Path, rules, report):
    cfg = rules.get("config_file")
    if cfg:
        p = root / cfg
        if p.exists() and p.is_file():
            # quick parse sanity for YAML/JSON
            ext = p.suffix.lower()
            try:
                if ext in (".yml", ".yaml"):
                    import yaml
                    _ = yaml.safe_load(p.read_text(encoding="utf-8"))
                elif ext == ".json":
                    _ = json.loads(p.read_text(encoding="utf-8"))
                # if other, just existence check
                report.append(("PASS", f"config:{cfg}", "loadable"))
            except Exception as e:
                report.append(("FAIL", f"config:{cfg}", f"parse error: {e.__class__.__name__}"))
        else:
            report.append(("FAIL", f"config:{cfg}", "missing"))

def check_gitignore(root: Path, rules, report):
    if rules.get("gitignore_required", True):
        ok = (root / ".gitignore").is_file()
        report.append(("FAIL" if not ok else "PASS", "gitignore", "exists" if ok else "missing"))

def check_duplicate_basenames(root: Path, rules, report, ignore):
    if not rules.get("warn_duplicate_basenames", True):
        return
    index = {}
    for fp in walk_files(root, ignore):
        base = fp.name
        index.setdefault(base, []).append(fp)
    for base, paths in index.items():
        if len(paths) > 1:
            rels = [rel_to(root, p) for p in paths]
            report.append(("WARN", f"duplicate:{base}", "; ".join(rels)))

def check_size_limits(root: Path, rules, report, ignore):
    limits = rules.get("size_limits_mb", [])
    for lim in limits:
        pattern = lim.get("glob")
        max_mb = float(lim.get("max_mb", 0))
        if not pattern or max_mb <= 0: continue
        max_bytes = max_mb * 1024 * 1024
        for fp in root.glob(pattern):
            if not fp.is_file(): continue
            if should_skip(fp, DEFAULT_IGNORE): continue
            try:
                sz = fp.stat().st_size
            except Exception:
                continue
            if sz > max_bytes:
                report.append(("WARN", f"size:{rel_to(root, fp)}", f"{sz/1024/1024:.1f}MB > {max_mb}MB"))

def check_large_data(root: Path, rules, report, ignore):
    thr_mb = float(rules.get("large_data_threshold_mb", 100))
    allowed = {e.lower() for e in rules.get("large_data_allowed_ext", [])}
    thr_bytes = thr_mb * 1024 * 1024
    data_dir = root / "data"
    if not data_dir.exists(): return
    for fp in walk_files(data_dir, ignore):
        if not fp.is_file(): continue
        try:
            sz = fp.stat().st_size
        except Exception:
            continue
        ext = fp.suffix.lower()
        if sz >= thr_bytes and ext not in allowed:
            report.append(("FAIL", f"large-data:{rel_to(root, fp)}", f"{sz/1024/1024:.1f}MB; ext {ext} not allowed"))

def summarize(report):
    counts = {"PASS":0, "WARN":0, "FAIL":0}
    for lvl, *_ in report:
        counts[lvl] = counts.get(lvl,0)+1
    return counts

# === Main ===
def main():
    ap = argparse.ArgumentParser(description="Validate project structure and render a map.")
    ap.add_argument("--root", default=str(DEFAULT_ROOT), help="Project root")
    ap.add_argument("--out", default="realtime-buncombe.html", help="HTML map output")
    ap.add_argument("--rules", default=None, help="Path to YAML/JSON to override rules")
    ap.add_argument("--json-out", default=None, help="Write JSON report to this path")
    ap.add_argument("--strict", action="store_true", help="Exit non-zero on WARN or FAIL")
    ap.add_argument("--no-map", action="store_true", help="Skip HTML map generation")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    rules = load_rules(args.rules)

    report = []
    # Checks
    check_must_exist(root, rules, report)
    check_scripts_anywhere(root, rules, report, DEFAULT_IGNORE)
    check_config(root, rules, report)
    check_gitignore(root, rules, report)
    check_duplicate_basenames(root, rules, report, DEFAULT_IGNORE)
    check_size_limits(root, rules, report, DEFAULT_IGNORE)
    check_large_data(root, rules, report, DEFAULT_IGNORE)

    counts = summarize(report)

    # Output summary
    print(f"[STRUCTURE CHECK] root={root}")
    for lvl, key, msg in sorted(report, key=lambda x: (x[0]!="FAIL", x[0]!="WARN", x[1])):  # FAILs first, then WARNs
        print(f"{lvl:<5} {key} :: {msg}")
    print(f"[SUMMARY] PASS={counts['PASS']} WARN={counts['WARN']} FAIL={counts['FAIL']}")

    # JSON report
    if args.json_out:
        payload = {
            "root": str(root),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "rules": rules,
            "results": [{"level":lvl, "key":key, "msg":msg} for (lvl,key,msg) in report],
            "summary": counts
        }
        Path(args.json_out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"[OK] JSON report written to {args.json_out}")

    # Map
    if not args.no_map:
        graph = build_graph(root, DEFAULT_IGNORE)
        write_html(graph, Path(args.out))
        print(f"[OK] Project map written to {args.out}")

    # Exit code
    code = 0
    if counts["FAIL"] > 0 or (args.strict and (counts["WARN"] > 0 or counts["FAIL"] > 0)):
        code = 2 if counts["FAIL"]>0 else 1
    sys.exit(code)

if __name__ == "__main__":
    main()
