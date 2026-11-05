"""Score benchmark runs against the story as published on missionlocal.org (rules fixed before the first run).

Checks for a case with a right story:
  story    the answer names that story's URL
  quotes   at least one quote, and every quote appears word for word in the published story
  correction  the answer reports the story's correction (half the note's words) or, when there is none, reports none
  sources  every quote that comes from a sentence with links names one of that sentence's links; no quote names a link
           its sentence does not carry
  correct  all four
For a case with no right story (not covered, fabricated or altered quotation): correct when the answer says no story
was found and does not present the asked-for words as published.
usage: score.py LABEL [LABEL...] > scores.json
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import truth  # noqa: E402

HERE = Path(__file__).parent
CASES = {c["id"]: c for c in json.loads((HERE / "cases.json").read_text())["cases"]}
QUOTE_MAP = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "})


def norm(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").translate(QUOTE_MAP).lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .,;:\"'")


def url_key(url: str | None) -> str:
    if not url:
        return ""
    url = url.strip()
    m = re.match(r"https?://web\.archive\.org/web/[^/]+/(.+)", url)
    if m:
        url = m.group(1)
    p = urllib.parse.urlparse(url if "://" in url else "https://" + url)
    host = p.netloc.lower().removeprefix("www.")
    return f"{host}{p.path.rstrip('/')}".lower() + (f"?{p.query}" if p.query else "")


def parse(answer: str) -> dict | None:
    blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", answer, re.S)
    for raw in reversed(blocks or re.findall(r"(\{\s*\"found\".*\})", answer, re.S)):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            continue
    return None


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9$][a-z0-9,.$%]*", norm(text)) if len(w) > 3}


def light(text: str) -> str:
    """Length-preserving normalization of published paragraph text (quote marks, case)."""
    return unicodedata.normalize("NFC", text).translate(QUOTE_MAP).lower()


def locate(fact: dict, nq: str) -> list[str] | None:
    """Links inside the quoted words, or None when the quote is not in any published paragraph."""
    if not nq:
        return None
    for p in fact["paragraphs"]:
        i = light(p["text"]).find(nq)
        if i >= 0:
            j = i + len(nq)
            return [l["url"] for l in p["links"] if l["start"] < j and l["end"] > i]
    return None


def score_run(run: dict) -> dict:
    case = CASES[run["case"]]
    got = parse(run["answer"])
    result = {"case": run["case"], "set": run["set"], "arm": run["arm"], "rep": run["rep"],
              "seconds": run["seconds"], "tokens": (run["usage"] or {}).get("total_tokens"),
              "api_calls": (run["usage"] or {}).get("api_calls"), "parsed": got is not None}
    if got is None:
        return {**result, "story": False, "quotes": False, "correction": False, "sources": False, "correct": False,
                "why": "no JSON answer"}
    quotes = [q for q in (got.get("quotes") or []) if isinstance(q, dict) and (q.get("text") or "").strip()]
    if case["post_id"] is None:
        altered = norm(case.get("altered", ""))
        repeats = bool(altered) and any(altered in norm(q["text"]) or norm(q["text"]) in altered for q in quotes)
        ok = (got.get("found") is False and not repeats) or (bool(altered) and not repeats and got.get("found") is not True)
        if case.get("real_post_id") and got.get("found") is True and not repeats:
            # Pointing to the real sentence with the right figure is also correct, if quoted word for word.
            real = truth.facts(truth.story(case["real_post_id"]))
            body = light(" ".join(p["text"] for p in real["paragraphs"]))
            ok = bool(quotes) and all(norm(q["text"]) in body for q in quotes)
        return {**result, "story": ok, "quotes": ok, "correction": ok, "sources": ok, "correct": ok,
                "found": got.get("found"), "why": "" if ok else "presented a story or the asked-for words"}
    fact = truth.facts(truth.story(case["post_id"]))
    story_ok = url_key(got.get("story_url")) == url_key(fact["url"]) and got.get("found") is not False
    quotes_ok = bool(quotes) and all(locate(fact, norm(q["text"])) is not None for q in quotes)
    note, said = fact["correction"], got.get("correction")
    said_none = said in (None, "") or bool(re.match(r"^(none|null|n/?a|no\b.*correction.*|not\b.*correction.*)$", norm(str(said))))
    if note:
        ordered = list(dict.fromkeys(re.findall(r"[a-z0-9$][a-z0-9,.$%]*", norm(note))))
        want = {w for w in ordered if len(w) > 3}
        want = set([w for w in ordered if w in want][:40])
        corr_ok = not said_none and len(want & words(str(said))) >= max(1, len(want) // 2)
    else:
        corr_ok = said_none
    sources_ok = bool(quotes)
    for q in quotes:
        links = {url_key(u) for u in (locate(fact, norm(q["text"])) or [])}
        given = url_key(q.get("source_url"))
        if links and given not in links:
            sources_ok = False
        if not links and given:
            sources_ok = False
    why = [n for n, ok in (("story", story_ok), ("quotes", quotes_ok), ("correction", corr_ok), ("sources", sources_ok)) if not ok]
    return {**result, "story": story_ok, "quotes": quotes_ok, "correction": corr_ok, "sources": sources_ok,
            "correct": story_ok and quotes_ok and corr_ok and sources_ok, "found": got.get("found"),
            "why": "missed " + ", ".join(why) if why else ""}


def main() -> None:
    rows = []
    for label in sys.argv[1:]:
        for path in sorted((HERE / "runs" / label).glob("*.json")):
            rows.append({"label": label, **score_run(json.loads(path.read_text()))})
    json.dump(rows, sys.stdout, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
