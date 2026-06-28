# TraceFly Issue Handbook

All issues encountered during development, with root cause analysis, fixes applied, and post-fix outcomes.

**Filter by type tag:** `[ENV]` `[CLI]` `[ADK]` `[ORCHESTRATION]` `[PERFORMANCE]` `[COST]`

---

## Issue #1 — `[ENV]` ModuleNotFoundError: No module named 'dotenv'

**Date:** 2026-06-28
**Type:** `[ENV]` — Environment / Setup

**Symptom:**
```
Traceback (most recent call last):
  File "test_setup.py", line 2, in <module>
    from dotenv import load_dotenv
ModuleNotFoundError: No module named 'dotenv'
```

**Root Cause:**
`python3` was invoked directly from the system Python, not from inside the virtual environment where packages were installed with `uv pip install -r requirements.txt`. The system Python has no knowledge of `.venv/lib/`.

**Fix Applied:**
Activate the virtual environment before running any Python command:
```bash
source .venv/bin/activate
python test_setup.py
```

The prompt changes to show `(.venv)` when the venv is active.

**Files Changed:** None — user workflow fix only.

**Outcome:**
`test_setup.py` runs successfully, confirms Claude API connection and Postgres connection with green checkmarks.

---

## Issue #2 — `[CLI]` source command with script argument ignored

**Date:** 2026-06-28
**Type:** `[CLI]` — CLI / Command Usage

**Symptom:**
Running `source .venv/bin/activate python demo/load_demo_data.py --limit 200` appeared to succeed (no error) but the script never actually ran.

**Root Cause:**
`source` (also written as `.`) only accepts a single argument — the file to source. Everything after `.venv/bin/activate` was silently discarded by the shell. The venv activated, but the script was never executed.

**Fix Applied:**
Run as two separate commands:
```bash
source .venv/bin/activate
python demo/load_demo_data.py --limit 200
```

**Files Changed:** None — user workflow fix only.

**Outcome:**
Demo loader downloads the Bitext dataset and loads traces into the database correctly.

---

## Issue #3 — `[CLI]` Permission denied running .py file directly

**Date:** 2026-06-28
**Type:** `[CLI]` — CLI / Command Usage

**Symptom:**
```
zsh: permission denied: demo/load_demo_data.py
```

**Root Cause:**
Running a Python script as a direct executable (`./script.py`) requires the file to have the executable bit set (`chmod +x`). Python files created by the Write tool do not have this bit. The shell tried to execute the file as a binary rather than passing it to the Python interpreter.

**Fix Applied:**
Always prefix with `python`:
```bash
python demo/load_demo_data.py --limit 200
```

**Files Changed:** None — user workflow fix only.

**Outcome:**
Script executes normally through the Python interpreter.

---

## Issue #4 — `[ADK]` ValueError: No root_agent found for 'test_agent'

**Date:** 2026-06-28
**Type:** `[ADK]` — Google ADK Configuration

**Symptom:**
```
ValueError: No root_agent found for 'test_agent'.
Searched in 'test_agent.agent.root_agent', 'test_agent.root_agent'
and 'test_agent/root_agent.yaml'.
```

**Root Cause:**
`adk web .` scans every subdirectory that contains an `__init__.py` and attempts to load it as an ADK agent. The `test_agent/` folder was created with `__init__.py` (making it a Python package) but only contained `example_integration.py` — no `root_agent`. ADK found the folder, tried to load it, and raised a `ValueError`.

**Fix Applied:**
Deleted `test_agent/__init__.py`. Without `__init__.py`, ADK does not treat the folder as a Python package and skips it entirely. `example_integration.py` still works as a standalone script.

**Files Changed:**
- `test_agent/__init__.py` — deleted

**Outcome:**
`adk web .` loads only `tracefly_agent` correctly. LiteLLM connects to `claude-haiku-4-5-20251001` successfully. ADK web UI opens cleanly at `http://localhost:8000`.

---

## Issue #5 — `[ORCHESTRATION]` No clusters found after enrichment

**Date:** 2026-06-28
**Type:** `[ORCHESTRATION]` — Agent Pipeline / Orchestration Logic

**Symptom:**
```
Step 2 — No clusters found. The traces may be too diverse or there
aren't enough similar failures to group together yet.
Steps 3, 4, and 5 cannot proceed without clusters.
```
Only 50 traces were enriched before clustering was attempted.

**Root Cause (two parts):**
1. The agent instruction said *"if it processes traces, proceed to step 2"* — so `enrich_traces()` was called exactly once (batch of 50 traces), then clustering ran immediately. With only 50 out of 1000 traces enriched, there weren't enough similar failures to form clusters.
2. `min_cluster_size=5` was too strict — HDBSCAN couldn't form groups of 5 from the limited enriched set.

**Fix Applied:**
1. Rewrote agent instruction to loop `enrich_traces()` until `remaining == 0`:
   > *"Call enrich_traces() REPEATEDLY. Keep calling until remaining == 0."*
2. Lowered `min_cluster_size` default from `5` → `3` in `cluster_traces()`.

**Files Changed:**
- `tracefly_agent/agent.py` — instruction rewritten
- `tracefly_agent/tools/cluster.py` — `min_cluster_size` default changed

**Outcome:**
Agent enriches all traces before clustering. HDBSCAN finds clusters for `refund_request` and `cancel_order` intent groups (the injected failure patterns in the demo data).

---

## Issue #6 — `[PERFORMANCE]` Trace enrichment too slow

**Date:** 2026-06-28
**Type:** `[PERFORMANCE]` — Speed / Throughput

**Symptom:**
Enrichment loop running for an impractically long time for 1000 demo traces. User had to stop the process mid-way.

**Root Cause:**
The original `enrich_traces()` processed traces in a sequential `for` loop:
- For each trace: 1 API call to classify intent + 1 API call to classify error mode (IO-bound, blocking)
- Embeddings generated one trace at a time with `model.encode(text)`
- DB writes after every single trace

1000 traces × ~2 API calls each = ~2000 sequential round-trips. With ~300ms latency per call, this takes ~10 minutes.

**Fix Applied (3-phase redesign):**

| Phase | Before | After |
|---|---|---|
| API classification | Sequential for loop | `ThreadPoolExecutor(max_workers=5)` — 5 concurrent |
| Embedding generation | `model.encode(text)` per trace | `model.encode(all_texts)` batch call once |
| DB writes | After every trace | Batch write after all processing |

Additional micro-optimizations:
- `batch_size` default: `50` → `100`
- `max_tokens` for label calls: `50` → `20` (labels are single words)

**Files Changed:**
- `tracefly_agent/tools/enrich.py` — full redesign with `ThreadPoolExecutor` and batch embedding

**Outcome:**
~5–10x throughput improvement per batch. 1000 traces now enriches in a fraction of the previous time.

---

## Issue #7 — `[COST]` claude-sonnet used everywhere instead of haiku

**Date:** 2026-06-28
**Type:** `[COST]` — Token / API Cost Optimization

**Symptom:**
User noted that enrichment was slow and raised the concern that sonnet was being used across the pipeline unnecessarily.

**Root Cause:**
The initial MVP draft used `claude-sonnet-4-6` for:
- Cluster description generation (`cluster.py`)
- Prompt proposal generation (`suggest.py`)
- The orchestrating ADK agent (`agent.py`)

Only per-trace classification in `enrich.py` was already using haiku. Sonnet is ~5x more expensive than haiku and not needed for classification-style or structured-output tasks.

**Fix Applied:**
Switched all model references to `claude-haiku-4-5-20251001`:

| File | Function | Was | Now |
|---|---|---|---|
| `cluster.py` | `_generate_cluster_description()` | sonnet | haiku |
| `suggest.py` | `_generate_proposals_for_cluster()` | sonnet | haiku |
| `agent.py` | `LiteLlm(model=...)` orchestrator | sonnet | haiku |

**Files Changed:**
- `tracefly_agent/tools/cluster.py`
- `tracefly_agent/tools/suggest.py`
- `tracefly_agent/agent.py`

**Outcome:**
All LLM calls now use Haiku. Estimated cost reduction ~80% compared to all-Sonnet. Full 1000-trace demo run costs cents rather than dollars.

---

## Issue #8 — `[ORCHESTRATION]` Agent stops after clustering, skips remaining steps

**Date:** 2026-06-28
**Type:** `[ORCHESTRATION]` — Agent Pipeline / Orchestration Logic

**Symptom:**
After clustering completed, the agent displayed cluster results and stopped. Steps 3 (score), 4 (suggest), and 5 (digest) were never called. When clustering was manually triggered mid-session, the agent had no context that it was part of a larger pipeline.

**Root Cause (two parts):**
1. Tool return values had no `"next_step"` field — Claude had to infer what to do next, and chose to stop and report.
2. The agent instruction contained *"if no clusters are found, report this and stop"* — Claude applied this too broadly, treating any clustering result as a stopping point rather than a pass-through.

**Fix Applied:**

**Part 1 — Add `next_step` to every tool return:**
Every tool now explicitly tells Claude what to call next:

| Tool | `next_step` value |
|---|---|
| `enrich_traces()` (has remaining) | `"Call enrich_traces() again — N traces still need enriching."` |
| `enrich_traces()` (done) | `"All traces enriched. Call cluster_traces(days_back=7, min_cluster_size=3)."` |
| `cluster_traces()` | `"Call score_clusters()"` |
| `score_clusters()` | `"Call generate_suggestions(top_n=3)"` |
| `generate_suggestions()` | `"Call send_digest()"` |

**Part 2 — Rewrite agent instruction with one core rule:**
> *"Every tool response contains a 'next_step' field. After EVERY tool call, read that field and immediately execute the instruction in it — no pausing, no asking the user, no summarizing mid-pipeline. Keep going until send_digest() completes."*

Steps 3–5 now always run regardless of whether clusters were found — they each handle the empty-cluster case gracefully.

**Files Changed:**
- `tracefly_agent/agent.py` — instruction rewritten
- `tracefly_agent/tools/enrich.py` — `next_step` added
- `tracefly_agent/tools/cluster.py` — `next_step` added
- `tracefly_agent/tools/score.py` — `next_step` added
- `tracefly_agent/tools/suggest.py` — `next_step` added

**Outcome:**
Pipeline always runs to completion. `send_digest()` executes after every run, printing the health summary, top clusters, and ranked proposals regardless of whether clusters were found.

---

## Quick Reference

| # | Type | Issue | Fix Summary |
|---|---|---|---|
| 1 | `[ENV]` | dotenv not found | Activate venv before running scripts |
| 2 | `[CLI]` | source ignores extra args | Use two separate commands |
| 3 | `[CLI]` | Permission denied on .py | Prefix with `python` |
| 4 | `[ADK]` | test_agent has no root_agent | Delete `test_agent/__init__.py` |
| 5 | `[ORCHESTRATION]` | No clusters found | Loop enrichment; lower min_cluster_size 5→3 |
| 6 | `[PERFORMANCE]` | Enrichment too slow | ThreadPoolExecutor + batch embedding |
| 7 | `[COST]` | Sonnet used everywhere | Switch all models to haiku |
| 8 | `[ORCHESTRATION]` | Agent stops after clustering | Add `next_step` to all tool returns; rewrite instruction |
