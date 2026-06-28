# TraceFly — Claude Code Context

## What This Project Is
TraceFly is an AI agent observability tool. It wraps any LLM agent, records every interaction as a trace, then runs a 5-step analysis pipeline to find failure patterns and suggest prompt fixes.

**Pipeline:** Observe → Enrich → Cluster → Score → Suggest → Digest

---

## Tech Stack
| Component | Choice | Why |
|---|---|---|
| Agent framework | Google ADK (Python) | LLM orchestration |
| LLM | Claude via LiteLLM | `LiteLlm(model="anthropic/claude-haiku-4-5-20251001")` |
| Database | Docker Postgres + pgvector | One command, no account needed |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2, 384 dims) | Free, runs locally |
| Clustering | hdbscan | No need to specify cluster count upfront |
| Demo data | Bitext Customer Support (Hugging Face) | 26K real support conversations, free |

**All LLM calls use `claude-haiku-4-5-20251001`.** Do not switch to Sonnet — it was changed globally to reduce cost.

---

## Python Environment
- Python **3.14** (`.venv/lib/python3.14/`)
- Package manager: `uv`
- **Always activate venv before running anything:**
  ```bash
  source .venv/bin/activate
  ```

---

## How to Run

### First time
```bash
source .venv/bin/activate
make setup       # starts Docker DB, runs schema, installs packages
# Add ANTHROPIC_API_KEY to .env
make demo        # loads 1000 Bitext traces + opens ADK web UI
```

### Daily
```bash
source .venv/bin/activate
make run         # opens ADK web UI at http://localhost:8000
# In chat: "Run the full analysis pipeline"
```

### Database
```bash
docker-compose up -d    # start
docker-compose down     # stop (data is preserved)
docker exec -it tracefly_db psql -U tracefly -d tracefly   # psql session
```

---

## Project Structure
```
Tracefly-Agent/
├── CLAUDE.md                       ← you are here
├── .env                            ← secrets (never commit)
├── .env.example                    ← safe template to commit
├── requirements.txt
├── docker-compose.yml
├── Makefile                        ← make setup / demo / run / db-*
├── README.md
├── test_setup.py                   ← verify Claude + DB connection
├── test_capture.py                 ← insert test traces
│
├── database/
│   ├── db.py                       ← get_db_connection() helper
│   └── schema.sql                  ← 4 tables: traces, clusters, proposals, digests
│
├── sdk/
│   └── capture.py                  ← capture_trace(), update_feedback(), trace_timer()
│
├── demo/
│   └── load_demo_data.py           ← downloads Bitext + loads traces with injected failures
│
├── tracefly_agent/
│   ├── agent.py                    ← root_agent (LlmAgent with 5 tools + pipeline instruction)
│   └── tools/
│       ├── enrich.py               ← Tool 1: classify intent/outcome/error_mode + embed
│       ├── cluster.py              ← Tool 2: HDBSCAN grouping + Claude descriptions
│       ├── score.py                ← Tool 3: impact_score = trace_count × severity_weight
│       ├── suggest.py              ← Tool 4: prompt before/after proposals with confidence score
│       └── digest.py               ← Tool 5: terminal summary (+ optional Slack)
│
├── test_agent/
│   └── example_integration.py     ← shows 5-line pattern to add TraceFly to any agent
│                                      (no __init__.py — intentional, see gotchas)
│
└── docs/
    └── issue_handbook.md           ← all bugs found + fixes applied with type tags
```

---

## Database
- **Connection:** `DATABASE_URL=postgresql://tracefly:tracefly_local@localhost:5432/tracefly`
- **Container name:** `tracefly_db`
- **4 tables:** `traces`, `clusters`, `proposals`, `digests`
- Embedding column: `vector(384)` using pgvector HNSW index
- Swappable to Supabase/Neon by changing `DATABASE_URL` in `.env` — nothing else changes

---

## Key Architecture Decisions

### Pipeline continuation via `next_step`
Every tool return dict includes a `"next_step"` field (e.g. `"Call score_clusters()"`). The agent instruction reads this field and executes it immediately. This is what keeps the pipeline running automatically end-to-end.

### Enrichment is concurrent
`enrich_traces()` uses `ThreadPoolExecutor(max_workers=5)` for Claude API calls (IO-bound) and batch-encodes all embeddings in one `model.encode(texts)` call. Default batch size is 100 traces per call.

### Enrichment loop
The agent calls `enrich_traces()` in a loop until `remaining == 0`. Do not change this to a single call — with 1000 traces and batch_size=100, it needs ~10 iterations.

### Clustering minimum
`cluster_traces(min_cluster_size=3)` — lowered from 5 to allow smaller datasets to form clusters.

---

## Known Gotchas

| Gotcha | Detail |
|---|---|
| `test_agent/__init__.py` must NOT exist | ADK scans all `__init__.py` folders as agents — `test_agent` has no `root_agent` so it would error. File was deleted. |
| Always use `python script.py`, never `./script.py` | .py files don't have executable bit set |
| `source .venv/bin/activate` must be its own command | `source activate python script.py` silently ignores the script |
| `adk web .` not `adk web tracefly_agent` | ADK takes the parent directory, not the agent folder |

Full issue log with root causes and fixes: `docs/issue_handbook.md`

---

## Build Plan Reference
Original full spec: `TraceFly_MVP_Build_Plan.md` (large — read in 400-line chunks)

| Phase | Section offset |
|---|---|
| Phase 0 — Environment | ~line 193 |
| Phase 1 — Database | ~line 408 |
| Phase 2 — SDK | ~line 634 |
| Phase 3 — Enrich | ~line 904 |
| Phase 4 — Cluster | ~line 1200 |
| Phase 5 — Score + Suggest | ~line 1499 |
| Phase 6 — Digest + Agent | ~line 1939 |
| Phase 7 — Demo Data | ~line 2194 |
| Phase 8 — Makefile | ~line 2507 |

---

## Current Status — 2026-06-28

### MVP: Complete
All 8 phases built and verified working.

| Phase | Status | Notes |
|---|---|---|
| 0 — Environment | Done | requirements.txt, docker-compose, .env.example, .gitignore |
| 1 — Database | Done | schema.sql (4 tables + vector index), db.py |
| 2 — SDK | Done | sdk/capture.py with PII masking, trace_timer |
| 3 — Enrich Tool | Done | Concurrent, haiku, batch embedding |
| 4 — Cluster Tool | Done | HDBSCAN, haiku descriptions, min_size=3 |
| 5 — Score + Suggest | Done | Rules-based scoring; haiku proposals with confidence score |
| 6 — Digest + Agent | Done | Terminal/Slack digest; pipeline auto-continues via next_step |
| 7 — Demo Data | Done | Bitext loader with injected failure rates |
| 8 — Makefile | Done | make setup / demo / run / db-* / clean |

### Post-MVP fixes applied
- Enrichment concurrent (ThreadPoolExecutor) — was sequential and slow
- All models switched to haiku — was sonnet in cluster/suggest/agent
- `next_step` field added to all tool returns — agent was stopping after clustering
- `test_agent/__init__.py` deleted — was causing ADK ValueError on startup
- `min_cluster_size` lowered 5→3 — was preventing cluster discovery on small datasets
- Agent instruction rewritten to loop enrichment — was calling once and moving on

### What's next (post-MVP)
- Add a UI / dashboard to browse clusters and proposals
- Add business event data to improve impact scoring
- NER-based PII masking (replace regex in sdk/capture.py)
- Scheduled runs via cron (enrich + cluster daily)
- Export proposals to Notion / Linear
