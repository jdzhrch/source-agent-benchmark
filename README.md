# Source agent benchmark: execution evidence

This repository holds the evidence for one benchmark claim. A reader's assistant that asks Mission Local's own agent over A2A gets fully correct answers more often than the same assistant using web search.

The report explains the design and the results. This repository holds the cases, the scripts and every raw run. All runs took place on 2026-11-04.

## Interface guide

`INTERFACE.md` is the guide for an agent that wants to call the outlet’s agent: access, requests, replies, the source package, signature checks, limits and errors. It was added on 2026-11-18, after the benchmark runs. The benchmark callers did not have it; they ran with the instructions in `callers/`.

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

## Setup to repeat it

1. Use Python 3.11 or later. The scripts need no extra packages. Scoring reads missionlocal.org, so it needs network access. `truth.py` caches each story in `cache/`.
2. Install Hermes Agent v0.22.7 and sign in to a provider that serves gpt-6-luna.
3. Create three Hermes profiles: `bench-outlet`, `bench-web` and `bench-a2a`. Give each one the matching file in `callers/` as its `SOUL.md`. Leave memory empty.
4. For `bench-outlet` and `bench-a2a`, add an A2A agent named `missionlocal` that points at `https://source-agent-905861176071.us-west1.run.app` with a subscriber credential.
5. Put the package verifier `source-verify` on the path that `callers/*.md` names.

Mission Local's agent, its subscriber credentials and the package verifier are part of the project and are not in this repository. The author can issue a test credential and share the verifier.

Two things will not match exactly on a rerun. Web search results change over time. `sample_cases.py` now counts paragraphs, while the original draw counted sentences with an earlier parser that was not kept, so `sampled.json` is the record of the stories actually drawn.

## Service versions

- Main test and first stress test: Mission Local's agent before the search change.
- `after_change`: the agent after the search change (committed and deployed at 18:55 EST on 2026-11-04). Each search also takes the best older matches and alternates them with recent ones.
- `clarify`: the same agent as `after_change`, with clarifying questions on or off.
