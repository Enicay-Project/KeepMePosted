#!/usr/bin/env python3
"""Liste les éléments collectés qui n'ont pas encore été analysés.

Usage : python scripts/pending.py [limite]
Sortie : JSON compact (une ligne par élément), du plus récent au plus ancien.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
limit = int(sys.argv[1]) if len(sys.argv) > 1 else 60

items = json.loads((ROOT / "data/items.json").read_text("utf-8"))
af = ROOT / "data/analyses.json"
analyses = json.loads(af.read_text("utf-8")) if af.exists() else {}

todo = [i for i in items if i["id"] not in analyses]
print(f"# {len(todo)} élément(s) à analyser, {min(limit, len(todo))} affiché(s)", file=sys.stderr)
for i in todo[:limit]:
    print(json.dumps({k: i[k] for k in ("id", "source_name", "zone", "category", "title", "summary", "published", "link")},
                     ensure_ascii=False))
