"""Aggregate scores.json into per-set tables. usage: summarize.py scores.json [label...]"""

from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict

rows = json.load(open(sys.argv[1]))
labels = sys.argv[2:] or sorted({r["label"] for r in rows})
for label in labels:
    sub = [r for r in rows if r["label"] == label]
    print(f"\n## {label}")
    print("| set | arm | runs | correct | story | quotes | correction | sources | median s | mean tokens | mean model calls |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    groups = defaultdict(list)
    for r in sub:
        groups[(r["set"], r["arm"])].append(r)
    for (s, a), rs in sorted(groups.items()):
        n = len(rs)
        pct = lambda k: f"{sum(1 for r in rs if r[k])}/{n}"
        toks = [r["tokens"] for r in rs if r["tokens"]]
        calls = [r["api_calls"] for r in rs if r["api_calls"]]
        print(f"| {s} | {a} | {n} | {pct('correct')} | {pct('story')} | {pct('quotes')} | {pct('correction')} | "
              f"{pct('sources')} | {statistics.median(r['seconds'] for r in rs):.0f} | "
              f"{statistics.mean(toks):,.0f} | {statistics.mean(calls):.1f} |" if toks and calls else
              f"| {s} | {a} | {n} | {pct('correct')} | - | - | - | - | - | - | - |")
    print("\nper case (correct runs out of runs):")
    cases = defaultdict(lambda: defaultdict(list))
    for r in sub:
        cases[r["case"]][r["arm"]].append(r)
    for c in sorted(cases):
        print(" ", c, "  ".join(f"{a}: {sum(1 for r in rs if r['correct'])}/{len(rs)} [{'; '.join(sorted({r['why'] for r in rs if r['why']}))}]"
                                for a, rs in sorted(cases[c].items())))
