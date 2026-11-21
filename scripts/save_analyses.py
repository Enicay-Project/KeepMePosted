#!/usr/bin/env python3
"""Fusionne un lot d'analyses dans data/analyses.json et, s'il y en a une, la synthèse du jour.

Usage : python scripts/save_analyses.py lot.json
lot.json :
{
  "analyses": {"<id>": {"resume": "...", "tags": [...], "exigences": [...],
                         "perimetre": "DAC|Entités|Les deux|Contexte", "score": 0-100,
                         "action": "...", "pourquoi": "..."}},
  "digest": {"date": "AAAA-MM-JJ", "synthese": "...", "une": [{"id": "...", "note": "..."}]}
}
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACTIONS = {"Rien", "Lire", "Suivre", "Informer le CISO", "Alerter une entité", "Ajuster la supervision"}
PERIMETRES = {"DAC", "Entités", "Les deux", "Contexte"}

batch = json.loads(Path(sys.argv[1]).read_text("utf-8"))
af = ROOT / "data/analyses.json"
df = ROOT / "data/digests.json"
analyses = json.loads(af.read_text("utf-8")) if af.exists() else {}
digests = json.loads(df.read_text("utf-8")) if df.exists() else {}
known = {i["id"] for i in json.loads((ROOT / "data/items.json").read_text("utf-8"))}

now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
errors = []
for iid, a in batch.get("analyses", {}).items():
    if iid not in known:
        errors.append(f"{iid}: identifiant inconnu")
        continue
    if a.get("action") not in ACTIONS:
        errors.append(f"{iid}: action invalide {a.get('action')!r}")
    if a.get("perimetre") not in PERIMETRES:
        errors.append(f"{iid}: périmètre invalide {a.get('perimetre')!r}")
    a["score"] = max(0, min(100, int(a.get("score", 0))))
    a["analysed_at"] = now
    analyses[iid] = a

if d := batch.get("digest"):
    for u in d.get("une", []):
        if u["id"] not in known:
            errors.append(f"une {u['id']}: identifiant inconnu")
    digests[d["date"]] = d

af.write_text(json.dumps(analyses, ensure_ascii=False, indent=1), "utf-8")
df.write_text(json.dumps(digests, ensure_ascii=False, indent=1), "utf-8")
print(f"{len(batch.get('analyses', {}))} analyse(s) fusionnée(s), total {len(analyses)}.")
if errors:
    print("Avertissements :\n  " + "\n  ".join(errors))
