#!/usr/bin/env python3
"""Collecte des sources de veille KeepMePosted.

Lit sources.yaml, interroge chaque source et met à jour :
  data/items.json   éléments collectés (dédoublonnés, conservés RETENTION_DAYS jours)
  data/status.json  état de chaque source à la dernière collecte
  data/state/       mémoire des liens vus et du texte des pages surveillées

Aucune dépendance hors PyYAML. Prévu pour tourner dans une GitHub Action.
"""
from __future__ import annotations

import difflib
import email.utils
import hashlib
import html
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
STATE = DATA / "state"
ITEMS_FILE = DATA / "items.json"
STATUS_FILE = DATA / "status.json"
RETENTION_DAYS = 120
FIRST_RUN_LIMIT = 8  # au premier passage d'une page "links", n'en garder que les N premiers
TIMEOUT = 30
UA = "Mozilla/5.0 (X11; Linux x86_64) KeepMePosted/1.0 (veille OSINT personnelle)"

NOW = datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def item_id(link: str, title: str = "") -> str:
    return hashlib.sha1((link or title).encode("utf-8")).hexdigest()[:16]


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "fr,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        raw = r.read()
        charset = r.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def clean(text: str | None, limit: int = 600) -> str:
    if not text:
        return ""
    text = html.unescape(TAG_RE.sub(" ", text))
    text = WS_RE.sub(" ", text).strip()
    return text[:limit]


def parse_date(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    try:
        return iso(email.utils.parsedate_to_datetime(value))
    except (TypeError, ValueError):
        pass
    try:
        return iso(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None


# ---------------------------------------------------------------- RSS / Atom
def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def child_text(el, *names):
    for c in el:
        if local(c.tag) in names and (c.text or "").strip():
            return c.text
    return None


def collect_rss(src: dict) -> list[dict]:
    root = ET.fromstring(fetch(src["url"]).encode("utf-8"))
    out = []
    for el in root.iter():
        name = local(el.tag)
        if name not in ("item", "entry"):
            continue
        title = clean(child_text(el, "title"), 300)
        link = None
        for c in el:
            if local(c.tag) == "link":
                link = (c.text or "").strip() or c.attrib.get("href")
                if link:
                    break
        summary = clean(child_text(el, "description", "summary", "content"))
        date = parse_date(child_text(el, "pubdate", "published", "updated", "date"))
        if not (title or link):
            continue
        out.append({"title": title, "link": link, "summary": summary, "published": date})
    return out


# ---------------------------------------------------------------- Liens d'une page
class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, clean(" ".join(self._text), 300)))
            self._href = None


def collect_links(src: dict, state: dict) -> list[dict]:
    p = LinkParser()
    p.feed(fetch(src["url"]))
    pattern = re.compile(src["match"]) if src.get("match") else None
    base = src["url"]
    found, seen_now = [], set()
    for href, text in p.links:
        if not href or href.startswith(("#", "mailto:", "javascript:", "tel:")):
            continue
        url = urllib.parse.urljoin(base, href).split("#")[0]
        if url.rstrip("/") == base.rstrip("/") or url in seen_now:
            continue
        if pattern and not pattern.search(url):
            continue
        if len(text) < 20:  # liens de menu, pagination, icônes
            continue
        seen_now.add(url)
        found.append({"title": text, "link": url, "summary": "", "published": None})

    known = set(state.get("seen", []))
    first_run = not known
    new = [f for f in found if f["link"] not in known]
    state["seen"] = sorted(known | seen_now)[-3000:]
    state["raw_links"], state["matched"] = len(p.links), len(found)
    if first_run:
        new = new[:FIRST_RUN_LIMIT]
    return new


# ---------------------------------------------------------------- Page surveillée
class TextParser(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            t = data.strip()
            if t:
                self.parts.append(WS_RE.sub(" ", t))


def collect_page(src: dict, state_dir: Path) -> list[dict]:
    p = TextParser()
    p.feed(fetch(src["url"]))
    lines = [l for l in p.parts if len(l) > 2]
    text = "\n".join(lines)
    snap = state_dir / f"{src['id']}.txt"
    previous = snap.read_text("utf-8") if snap.exists() else None
    snap.write_text(text, "utf-8")
    if previous is None or previous == text:
        return []
    added = [l[2:] for l in difflib.ndiff(previous.splitlines(), lines) if l.startswith("+ ")]
    removed = [l[2:] for l in difflib.ndiff(previous.splitlines(), lines) if l.startswith("- ")]
    if not added and not removed:
        return []
    summary = "Ajouté : " + " | ".join(added)[:450] if added else ""
    if removed:
        summary += (" — " if summary else "") + "Retiré : " + " | ".join(removed)[:150]
    stamp = NOW.strftime("%Y-%m-%d")
    return [{
        "title": f"Page modifiée : {src['name']}",
        "link": src["url"] + f"#maj-{stamp}",
        "summary": summary,
        "published": iso(NOW),
    }]


# ---------------------------------------------------------------- Principal
def keep(entry: dict, keywords: list[str] | None) -> bool:
    if not keywords:
        return True
    hay = f"{entry['title']} {entry['summary']}".lower()
    return any(re.search(r"(?<![a-z])" + re.escape(k.lower()) + r"(?![a-z])", hay) for k in keywords)


def main() -> int:
    STATE.mkdir(parents=True, exist_ok=True)
    cfg = yaml.safe_load((ROOT / "sources.yaml").read_text("utf-8"))
    sources = cfg["sources"]
    only = set(sys.argv[1:])

    items = {i["id"]: i for i in json.loads(ITEMS_FILE.read_text("utf-8"))} if ITEMS_FILE.exists() else {}
    status = json.loads(STATUS_FILE.read_text("utf-8")) if STATUS_FILE.exists() else {}
    links_state_file = STATE / "links.json"
    links_state = json.loads(links_state_file.read_text("utf-8")) if links_state_file.exists() else {}

    total_new = 0
    for src in sources:
        if only and src["id"] not in only:
            continue
        sid = src["id"]
        prev = status.get(sid, {})
        try:
            if src["type"] == "rss":
                entries = collect_rss(src)
            elif src["type"] == "links":
                entries = collect_links(src, links_state.setdefault(sid, {}))
            elif src["type"] == "page":
                entries = collect_page(src, STATE)
            else:
                raise ValueError(f"type inconnu : {src['type']}")
            entries = [e for e in entries if keep(e, src.get("keywords"))]
            new = 0
            for e in entries:
                iid = item_id(e["link"], e["title"])
                if iid in items:
                    continue
                items[iid] = {
                    "id": iid,
                    "source": sid,
                    "source_name": src["name"],
                    "category": src.get("category", ""),
                    "zone": src.get("zone", ""),
                    "title": e["title"],
                    "link": e["link"],
                    "summary": e["summary"],
                    "published": e["published"] or iso(NOW),
                    "collected": iso(NOW),
                }
                new += 1
            total_new += new
            status[sid] = {"name": src["name"], "url": src["url"], "ok": True, "new": new,
                           "error": None, "last_ok": iso(NOW), "checked": iso(NOW)}
            if src["type"] == "links":
                ls = links_state[sid]
                status[sid]["links"] = f"{ls.get('matched', 0)}/{ls.get('raw_links', 0)}"
                if not ls.get("raw_links"):
                    status[sid]["error"] = "Aucun lien trouvé : page probablement générée en JavaScript"
            print(f"[ok]     {sid:20} +{new}")
        except Exception as exc:  # une source en panne ne bloque pas les autres
            msg = f"{type(exc).__name__}: {exc}"[:300]
            status[sid] = {"name": src["name"], "url": src["url"], "ok": False, "new": 0,
                           "error": msg, "last_ok": prev.get("last_ok"), "checked": iso(NOW)}
            print(f"[erreur] {sid:20} {msg}")

    # retirer les sources supprimées du registre
    ids = {s["id"] for s in sources}
    status = {k: v for k, v in status.items() if k in ids}

    cutoff = iso(NOW - timedelta(days=RETENTION_DAYS))
    kept = [i for i in items.values() if (i.get("published") or i["collected"]) >= cutoff]
    kept.sort(key=lambda i: i.get("published") or "", reverse=True)

    ITEMS_FILE.write_text(json.dumps(kept, ensure_ascii=False, indent=1), "utf-8")
    STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=1), "utf-8")
    links_state_file.write_text(json.dumps(links_state, ensure_ascii=False, indent=0), "utf-8")
    print(f"Total : {len(kept)} éléments, {total_new} nouveaux.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
