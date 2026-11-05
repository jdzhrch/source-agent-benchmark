"""Run benchmark cases through the two caller arms (same Hermes harness, same weak model).

usage: run.py LABEL SETS ARMS REPS [WORKERS]
  e.g. run.py main tuning,main outlet,web 3 6
Each run is saved to runs/LABEL/<case>_<arm>_<rep>.json with the answer, wall time and token usage.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).parent
MODEL, REASONING = "gpt-6-luna", "low"
ARMS = {"outlet": ("bench-outlet", "a2a,terminal"), "web": ("bench-web", "web"),
        # Same caller for both; the outlet agent runs with clarifying questions on or off (SOURCE_AGENT_CLARIFY).
        "clarify_on": ("bench-a2a", "a2a,terminal"), "clarify_off": ("bench-a2a", "a2a,terminal")}
TIMEOUT = 360


def prompt(case: dict) -> str:
    text = case["question"]
    if case.get("private"):
        text += f"\n\n(Private notes about the reader, for you only: {case['private']})"
    if case.get("context"):
        text += f"\n\n(What the reader cares about, for you only: {case['context']})"
    return text


def one(label: str, case: dict, arm: str, rep: int) -> str:
    out = HERE / "runs" / label / f"{case['id']}_{arm}_{rep}.json"
    if out.exists():
        return f"skip {out.name}"
    profile, toolsets = ARMS[arm]
    with tempfile.TemporaryDirectory() as work:
        usage = Path(work) / "usage.json"
        cmd = ["hermes", "-p", profile, "-z", prompt(case), "-m", MODEL, "--reasoning", REASONING,
               "-t", toolsets, "--in", work, "--usage-file", str(usage)]
        start = time.monotonic()
        try:
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
            answer, err, code = done.stdout, done.stderr[-2000:], done.returncode
        except subprocess.TimeoutExpired as exc:
            answer, err, code = (exc.stdout or b"").decode() if isinstance(exc.stdout, bytes) else (exc.stdout or ""), "timeout", -9
        seconds = round(time.monotonic() - start, 1)
        used = json.loads(usage.read_text()) if usage.exists() else {}
    record = {"case": case["id"], "set": case["set"], "arm": arm, "rep": rep, "model": MODEL,
              "reasoning": REASONING, "started": datetime.now(UTC).isoformat(timespec="seconds"),
              "seconds": seconds, "exit": code, "stderr_tail": err, "answer": answer,
              "usage": {k: used.get(k) for k in ("input_tokens", "output_tokens", "cache_read_tokens",
                                                  "reasoning_tokens", "total_tokens", "api_calls", "session_id")}}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=1, ensure_ascii=False))
    return f"{out.name} {seconds}s exit {code}"


def main() -> None:
    label, sets, arms, reps = sys.argv[1], sys.argv[2].split(","), sys.argv[3].split(","), int(sys.argv[4])
    workers = int(sys.argv[5]) if len(sys.argv) > 5 else 6
    cases = [c for c in json.loads((HERE / "cases.json").read_text())["cases"] if c["set"] in sets]
    jobs = [(c, a, r) for r in range(1, reps + 1) for c in cases for a in arms]
    print(f"{len(jobs)} runs", flush=True)
    with ThreadPoolExecutor(workers) as pool:
        for line in pool.map(lambda j: one(label, *j), jobs):
            print(line, flush=True)


if __name__ == "__main__":
    main()
