#!/usr/bin/env python3
"""Construit la page publiée : dist/index.html et dist/data.json."""
import json
import re
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"


def load(name, default):
    p = ROOT / "data" / name
    return json.loads(p.read_text("utf-8")) if p.exists() else default


# Score provisoire tant qu'un élément n'est pas analysé
BOOST = re.compile(r"part-is|nis ?2|easa|cargolux|luxair|lux-airport|findel|\bana\b|\bdac\b|"
                   r"ransomware|cyberattack|cyberattaque|gnss|spoofing|jamming|brouillage|sita|collins", re.I)


def provisional_score(i):
    s = {"LU": 45, "EU": 35, "INT": 25}.get(i.get("zone"), 25)
    s += 10 * min(3, len(BOOST.findall(f"{i['title']} {i['summary']}")))
    return min(s, 70)


def main():
    items = load("items.json", [])
    analyses = load("analyses.json", {})
    digests = load("digests.json", {})
    status = load("status.json", {})
    cal = yaml.safe_load((ROOT / "calendar.yaml").read_text("utf-8")) or []
    for c in cal:
        if isinstance(c.get("date"), date):
            c["date"] = c["date"].isoformat()

    out = []
    for i in items:
        a = analyses.get(i["id"])
        row = dict(i)
        if a:
            row["a"] = {k: a.get(k) for k in ("resume", "tags", "exigences", "perimetre", "score", "action", "pourquoi", "doublon_de")}
        else:
            row["p"] = provisional_score(i)
        row.pop("collected", None)
        out.append(row)

    latest = max(digests) if digests else None
    data = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "items": out,
        "digest": digests.get(latest) if latest else None,
        "calendar": cal,
        "sources": [dict(id=k, **v) for k, v in status.items()],
    }
    DIST.mkdir(exist_ok=True)
    (DIST / "data.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), "utf-8")
    shutil.copy(ROOT / "web/index.html", DIST / "index.html")
    print(f"dist/ : {len(out)} éléments ({sum(1 for r in out if 'a' in r)} analysés), digest {latest}")


if __name__ == "__main__":
    main()
