# Source agent benchmark: execution evidence

This repository holds the evidence for one benchmark claim. A reader's assistant that asks Mission Local's own agent over A2A gets fully correct answers more often than the same assistant using web search.

The report explains the design and the results. This repository holds the cases, the scripts and every raw run. All runs took place on 2026-11-04.

## Files

| Path | Contents |
|---|---|
| `cases.json` | All 29 cases, written before the first scored run. The field `set` is `tuning`, `main`, `stress_a`, `stress_b` or `clarify`. |
| `sample_cases.py`, `sampled.json` | How the fresh cases were drawn from missionlocal.org (seed 20261104). |
| `run.py` | Runs each case through one caller arm. It saves the answer, the wall time and the caller's token usage. |
| `truth.py` | Reads each story as published on missionlocal.org and extracts its paragraphs, links and correction note. It shares no code with the system under test. |
| `score.py` | Scores each saved answer against the published story. The rules were fixed before the first run. |
| `summarize.py` | Prints the tables in the report. |
| `callers/` | The instructions each caller arm ran with. |
| `runs/<label>/<case>_<arm>_<rep>.json` | Every raw answer. Labels: `main`, `stress_before`, `after_change`, `clarify`. |
| `scores-*.json` | Per-run scores for each label. |
| `caller-sessions-*.jsonl.gz` | Full caller session transcripts with every tool call. |
| `outlet-agent-log-*.json` | The outlet agent's server log for each batch: searches, candidate stories, clarifying questions and chosen stories. |

## Arms

All arms use Hermes Agent v0.22.7 with gpt-6-luna at reasoning effort low, no memory and no reader persona.

| Arm | Caller instructions | Tools |
|---|---|---|
| `outlet` | `callers/bench-outlet.md` | A2A call to Mission Local's agent, plus a terminal used only for the package verifier |
| `web` | `callers/bench-web.md` | Web search and web page reading only |
| `clarify_on` | `callers/bench-a2a.md` | Same as `outlet`. The outlet agent may ask one clarifying question. |
| `clarify_off` | `callers/bench-a2a.md` | Same as `outlet`. The outlet agent runs with `SOURCE_AGENT_CLARIFY=0` and answers in one turn. |

## Commands used

```bash
python -I run.py main tuning,main outlet,web 3 6
python -I run.py stress_before stress_a,stress_b outlet,web 3 4
python -I run.py after_change stress_a,stress_b,tuning,main outlet 3 6
python -I run.py clarify clarify clarify_on 3 5 2
python -I run.py clarify clarify clarify_off 3 5 2
python -I score.py main > scores-main.json
python -I summarize.py scores-main.json
```

`score.py` and `summarize.py` take the other labels the same way.

## What you need to repeat it

- Hermes Agent with access to gpt-6-luna.
- For the outlet arms, a subscriber link to Mission Local's agent. Its public agent card is at `https://source-agent-905861176071.us-west1.run.app/.well-known/agent-card.json`. Subscriber credentials are not in this repository; the author can issue a test credential.
- Network access to missionlocal.org for scoring.

Web search results change over time, so a rerun of the `web` arm will not match these runs exactly.
