"""Draw fresh HW7 cases from missionlocal.org by a fixed rule and seed (run once, before any benchmark run)."""

from __future__ import annotations

import json
import random
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import truth  # noqa: E402

SEED = 20261104
TUNING = {567594, 784638, 757408}  # HW6 stories, used while building the system
DOC_HOSTS = ("sfgov.org", "sf.gov", "sfbos.org", "legistar.com", "documentcloud.org", "ca.gov", "courts.ca.gov")


def is_document(url: str) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower()
    return (host.endswith(".gov") or any(host.endswith(h) for h in DOC_HOSTS)
            or urllib.parse.urlparse(url).path.lower().endswith(".pdf"))


def summary(post: dict) -> dict:
    f = truth.facts(post)
    doc_sentences = sum(1 for s in f["sentences"] if any(is_document(u) for u in s["links"]))
    words = sum(len(s["text"].split()) for s in f["sentences"])
    return {"post_id": f["post_id"], "url": f["url"], "published": f["published"], "title": f["title"],
            "correction": f["correction"], "document_sentences": doc_sentences, "words": words}


def pool(params: dict[str, str], pages: list[int]) -> list[dict]:
    out = []
    for page in pages:
        posts, _ = truth.list_posts(**params, page=str(page))
        out += [summary(p) for p in posts if p["id"] not in TUNING]
    return out


def main() -> None:
    rng = random.Random(SEED)
    fields = {"_fields": "id,link,date,title,content", "per_page": "100", "orderby": "date"}
    # Rule 1: stories from 2023-2025 that carry a correction note.
    corr_params = {**fields, "search": "previous version", "after": "2023-01-01T00:00:00", "before": "2026-01-01T00:00:00"}
    _, corr_pages = truth.list_posts(**corr_params)
    corrections = [s for s in pool(corr_params, list(range(1, corr_pages + 1))) if s["correction"] and s["words"] >= 300]
    # Rule 2: stories from 2024-2025 with no correction and at least two sentences linking to a public document.
    doc_params = {**fields, "after": "2024-01-01T00:00:00", "before": "2026-01-01T00:00:00"}
    _, doc_pages = truth.list_posts(**doc_params)
    pages = sorted(rng.sample(range(1, doc_pages + 1), 4))
    documents = [s for s in pool(doc_params, pages) if not s["correction"] and s["document_sentences"] >= 2 and s["words"] >= 300]
    picked = {"seed": SEED, "rule_1_pool": len(corrections), "rule_2_pool": len(documents), "rule_2_pages": pages,
              "corrections": rng.sample(corrections, 6), "documents": rng.sample(documents, 6)}
    Path(sys.argv[1]).write_text(json.dumps(picked, indent=1, ensure_ascii=False))
    for k in ("corrections", "documents"):
        for s in picked[k]:
            print(k[:4], s["post_id"], s["published"], s["document_sentences"], "|", s["title"][:90], "|", (s["correction"] or "")[:80])
    print("pools:", picked["rule_1_pool"], picked["rule_2_pool"], "pages", pages)


if __name__ == "__main__":
    main()
