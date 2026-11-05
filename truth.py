"""Ground truth for HW7: the story as published on missionlocal.org, read from the public WordPress API."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import html
import re

API = "https://missionlocal.org/wp-json/wp/v2/posts"
CACHE = Path(__file__).parent / "cache"
CACHE.mkdir(exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (MAS.665 HW7 benchmark)"}


def get(url: str) -> tuple[object, dict[str, str]]:
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.loads(r.read()), dict(r.headers)
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def list_posts(**params: str) -> tuple[list[dict], int]:
    data, headers = get(f"{API}?{urllib.parse.urlencode(params)}")
    return data, int(headers.get("X-WP-TotalPages", "1"))  # type: ignore[return-value]


def story(post_id: int) -> dict:
    path = CACHE / f"{post_id}.json"
    if path.exists():
        return json.loads(path.read_text())
    data, _ = get(f"{API}/{post_id}?_fields=id,link,date,title,content")
    path.write_text(json.dumps(data))
    return data  # type: ignore[return-value]


_P = re.compile(r"<p\b[^>]*>(.*?)</p>", re.S | re.I)
_A = re.compile(r"<a\b[^>]*?href=\"([^\"]*)\"[^>]*>(.*?)</a>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")
_NOTE = re.compile(r"^(correction|clarification|editor.s note)\b|previous version|earlier version", re.I)


def _piece(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub("", fragment)))


def paragraphs(raw: str) -> list[dict]:
    """Visible text of each published paragraph and the character span of every link in it.
    Written independently of the source agent's own parser, so the check does not inherit its bugs."""
    out = []
    for m in _P.finditer(raw):
        inner, text, links, pos = m.group(1), "", [], 0
        for a in [*_A.finditer(inner), None]:
            chunk = _piece(inner[pos:a.start() if a else len(inner)])
            text += chunk.lstrip(" ") if text.endswith(" ") or not text else chunk
            if a is None:
                break
            anchor = _piece(a.group(2))
            anchor = anchor.lstrip(" ") if text.endswith(" ") or not text else anchor
            start = len(text)
            text += anchor
            links.append({"url": html.unescape(a.group(1)).strip(), "start": start, "end": len(text)})
            pos = a.end()
        if text.strip():
            out.append({"text": text, "links": links})
    return out


def facts(post: dict) -> dict:
    """What a correct answer must match: the published paragraphs with their links, and the correction note."""
    paras = paragraphs(post["content"]["rendered"])
    note = next((p["text"].strip() for p in paras if _NOTE.search(p["text"].strip())), None)
    return {
        "post_id": post["id"],
        "url": post["link"],
        "published": post["date"][:10],
        "title": html.unescape(post["title"]["rendered"]),
        "paragraphs": paras,
        "correction": note,
    }
