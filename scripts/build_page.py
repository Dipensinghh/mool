"""Embed bench/results.json into docs/index.html. Run after `python -m bench.run_bench`."""
import json, sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
repo = sys.argv[1] if len(sys.argv) > 1 else "https://github.com/YOUR_USERNAME/mool"
html = (root / "docs/template.html").read_text(encoding="utf-8")
bench = json.loads((root / "bench/results.json").read_text(encoding="utf-8"))
out = html.replace("__BENCH__", json.dumps(bench, ensure_ascii=False)).replace("__REPO__", repo)
(root / "docs/index.html").write_text(out, encoding="utf-8")
print("wrote docs/index.html")
