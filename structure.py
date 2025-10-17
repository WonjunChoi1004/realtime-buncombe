# structure.py
# Generates a universal map of the project structure.

import argparse, os, re, json, csv, sys, hashlib
from pathlib import Path
from datetime import datetime

# === CONFIG DEFAULTS ===
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
  "web":   { color:{background:"#fecaca"} },
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

def build_graph(root: Path, ignore_names):
    nodes, edges = [], []
    seen = set()

    def add_node(pid, label, group):
        if pid not in seen:
            seen.add(pid)
            nodes.append({"id": pid, "label": label, "group": group, "shape": "box"})

    def add_edge(a, b):
        edges.append({"from": a, "to": b, "arrows": "to"})

    add_node("root", root.name, "dir")

    for dirpath, dirnames, filenames in os.walk(root):
        dpath = Path(dirpath)
        if any(x in ignore_names for x in dpath.parts):
            continue
        did = f"dir:{rel_to(root, dpath)}" if dpath != root else "root"
        add_node(did, dpath.name + "/", "dir")
        for dn in dirnames:
            cpath = dpath / dn
            cid = f"dir:{rel_to(root, cpath)}"
            add_node(cid, dn + "/", "dir")
            add_edge(did, cid)
        for fn in filenames:
            if fn.startswith("."): continue
            fpath = dpath / fn
            fid = f"file:{rel_to(root, fpath)}"
            grp = classify(fpath)
            add_node(fid, fn, grp)
            add_edge(did, fid)
    return {"nodes": nodes, "edges": edges, "meta": {"root": str(root)}}

def write_html(graph: dict, out_path: Path):
    html = HTML_TEMPLATE.replace("__DATA__", json.dumps(graph, separators=(",", ":")))
    out_path.write_text(html, encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(DEFAULT_ROOT), help="Project root path")
    ap.add_argument("--out", default="ArcGISmap.html")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    graph = build_graph(root, DEFAULT_IGNORE)
    write_html(graph, Path(args.out))
    print(f"[OK] Project map written to {args.out}")

if __name__ == "__main__":
    main()
