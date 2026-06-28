# TraceFly MVP — Complete Project Execution Plan
### Build Guide for Non-Technical Founders
**Stack:** Google ADK (Python) · Claude (Anthropic) via LiteLLM · Docker Postgres + pgvector  
**Demo Data:** Bitext Customer Support Dataset (Hugging Face — free, public, no account needed)  
**Scope:** Observe → Analyze → Suggest  
**Estimated Build Time:** 6 weeks (part-time) or 3 weeks (full-time focus)

---

## Before You Start Reading This Plan

This document is written for someone who:
- Has learned Google ADK basics in Python
- Has an Anthropic Claude API key
- Is not deeply technical but can follow step-by-step Python code
- Wants to understand *why* every decision is made, not just what to do

Every section explains the decision first, then gives you the exact steps and code.

---

## Table of Contents

1. [The Database Decision — Docker vs Supabase](#1-the-database-decision)
2. [How the Whole System Fits Together](#2-how-the-whole-system-fits-together)
3. [Your Tech Stack — Final Choices and Why](#3-your-tech-stack)
4. [Project Folder Structure](#4-project-folder-structure)
5. [Phase 0 — Environment Setup (Day 1)](#5-phase-0--environment-setup)
6. [Phase 1 — Database Schema (Days 2–3)](#6-phase-1--database-schema)
7. [Phase 2 — Trace Capture SDK (Days 4–6)](#7-phase-2--trace-capture-sdk)
8. [Phase 3 — Enrichment Agent (Days 7–10)](#8-phase-3--enrichment-agent)
9. [Phase 4 — Clustering Agent (Days 11–15)](#9-phase-4--clustering-agent)
10. [Phase 5 — Suggestion Agent (Days 16–20)](#10-phase-5--suggestion-agent)
11. [Phase 6 — Digest Tool + Wiring It All Together (Days 21–25)](#11-phase-6--digest-and-wiring)
12. [Phase 7 — Demo Data Loader (Days 26–28)](#12-phase-7--demo-data-loader)
13. [Phase 8 — Makefile + One-Command Demo (Days 29–30)](#13-phase-8--makefile-and-one-command-demo)
14. [How to Run and Demo the System](#14-how-to-run-and-demo-the-system)
15. [Troubleshooting Common Problems](#15-troubleshooting-common-problems)
16. [What Comes After MVP](#16-what-comes-after-mvp)

---

## 1. The Database Decision

### Docker locally — Supabase optionally

The default setup uses **Docker** to run Postgres + pgvector on your own machine. One command starts the database, no account needed, no internet required, works offline. Any developer who clones your repo is running in minutes.

```bash
docker-compose up -d   # starts Postgres with pgvector, that's it
```

| | Docker (default) | Supabase (optional) |
|---|---|---|
| Setup time | 1 command | 5 mins + account |
| Works offline | Yes | No |
| Cost | Free | Free tier |
| Dashboard | None (use any Postgres viewer) | Built-in |
| For recruiters cloning repo | ✅ Instant | ❌ Must create account |
| For your own hosted version | Swap DATABASE_URL | Swap DATABASE_URL |

**Swapping is one line.** The entire codebase uses a `DATABASE_URL` environment variable. To switch from Docker to Supabase, change that one line in `.env`. Nothing else changes.

**Docker setup takes 2 minutes:**
1. Install Docker Desktop from docker.com (free)
2. Run `docker-compose up -d`
3. Done — Postgres is running on your machine

---

## 2. How the Whole System Fits Together

Before writing a single line of code, understand the big picture. Re-read this section whenever you feel lost.

```
BITEXT DATASET (Hugging Face — free, public)
       │
       │  demo/load_demo_data.py downloads + transforms it
       ▼
YOUR AGENT (any Python LLM agent you've already built)
       │
       │  You add 3 lines of code to your agent
       │  Those 3 lines call our lightweight SDK
       ▼
TRACE CAPTURE SDK  ← this is NOT an agent, just a simple function
       │
       │  Sends trace data to Postgres
       ▼
DOCKER POSTGRES + pgvector  ← runs on your machine, one command to start
       │
       │  TraceFly Analysis Agent reads from here
       ▼
TRACEFLY ANALYSIS AGENT  ← this IS a Google ADK agent
       │
       │  It has 4 tools (Python functions):
       │    Tool 1: enrich_traces()        — adds labels to raw traces
       │    Tool 2: cluster_traces()       — groups similar failures together
       │    Tool 3: score_clusters()       — ranks by impact
       │    Tool 4: generate_suggestions() — proposes prompt fixes
       │
       │  Results written back to Postgres
       ▼
DIGEST TOOL  ← a simple Python function, not an agent
       │
       │  Reads top clusters from Postgres
       │  Formats a summary
       │  Prints to terminal (or Slack if configured)
       ▼
YOU (reading the output and deciding what to fix)
```

**The key insight:** Your real agent never knows TraceFly exists. You just add a tiny wrapper that silently records what happens. TraceFly runs separately, on its own schedule, analyzing what it recorded.

---

## 3. Your Tech Stack

Here is every tool you will use and exactly why.

| Tool | What It Is | Why This One |
|---|---|---|
| **Python 3.11+** | Programming language | ADK requires Python 3.10+; 3.11 is stable and fast |
| **Google ADK** | Agent framework | You already know it; handles the LLM orchestration for us |
| **LiteLLM** | Model connector | Lets ADK use Claude instead of Gemini — one line of code |
| **Claude Sonnet (via Anthropic API)** | The LLM brain | Your existing API key; excellent reasoning for analysis tasks |
| **Docker Desktop** | Runs Postgres locally | One command, no account, works offline, anyone can clone and run |
| **pgvector/pgvector Docker image** | Postgres with vector support built in | Official image, no manual extension install needed |
| **sentence-transformers** | Embedding library | Converts text traces to vectors for clustering; free, runs locally |
| **hdbscan** | Clustering algorithm | Finds natural groups without needing to specify count upfront |
| **psycopg2** | Postgres connector | Python talks to the database through this |
| **datasets (Hugging Face)** | Dataset downloader | One line to download the Bitext demo dataset |
| **python-dotenv** | Environment variables | Keeps your API keys safe (never hardcode them) |
| **requests** | HTTP library | Sends the Slack digest |
| **uv** | Package manager | Faster than pip; recommended by Google ADK docs |

**What you do NOT need:**
- A Supabase account (Docker replaces it locally)
- A separate vector database (pgvector is built into the Docker image)
- Any paid services beyond your Anthropic API key
- A web server (ADK's built-in `adk web` is enough for testing)

---

## 4. Project Folder Structure

This is the exact folder layout you will create. ADK requires a specific structure — do not change it.

```
tracefly/
│
├── .env                          ← your API keys (never commit this to GitHub)
├── .env.example                  ← copy of .env with fake values — safe to share
├── .gitignore                    ← tells git to ignore .env and __pycache__
├── requirements.txt              ← list of Python packages to install
├── docker-compose.yml            ← starts Postgres + pgvector with one command
├── Makefile                      ← shortcuts: make setup, make demo, make run
├── README.md                     ← how to get started in 5 minutes
│
├── sdk/                          ← the trace capture code (NOT an agent)
│   ├── __init__.py
│   └── capture.py                ← the 3 lines you add to your agent
│
├── database/                     ← database setup scripts
│   ├── __init__.py
│   ├── db.py                     ← connection helper
│   └── schema.sql                ← creates all the tables
│
├── demo/                         ← everything needed for a one-command demo
│   ├── __init__.py
│   └── load_demo_data.py         ← downloads Bitext dataset + loads into DB
│
├── tracefly_agent/               ← THE ADK AGENT (must match folder name)
│   ├── __init__.py               ← required by ADK
│   ├── agent.py                  ← defines the ADK agent and its tools
│   └── tools/                   ← each tool is its own file
│       ├── __init__.py
│       ├── enrich.py             ← Tool 1: label traces
│       ├── cluster.py            ← Tool 2: group traces
│       ├── score.py              ← Tool 3: rank clusters
│       ├── suggest.py            ← Tool 4: generate prompt proposals
│       └── digest.py             ← sends the daily summary
│
└── test_agent/                   ← optional: connect your own agent
    ├── __init__.py
    └── example_integration.py    ← shows how to add TraceFly to any agent
```

**Why this structure?**  
ADK looks for a folder that contains `agent.py` and `__init__.py`. The folder name becomes the agent name. Everything else (`sdk/`, `database/`, `demo/`, `tools/`) is supporting code that the agent imports. The `demo/` folder and `Makefile` are purely for making the project easy to try — they are not part of the core system.

---

## 5. Phase 0 — Environment Setup

**Goal:** Python running, packages installed, Supabase connected, Claude API working.  
**Time:** Half a day.

---

### Step 5.1 — Install Python and uv

Open your terminal (Terminal on Mac, Command Prompt on Windows).

Check if Python is installed:
```bash
python --version
```

You need Python 3.11 or higher. If not installed, download from python.org.

Install `uv` (faster package manager, recommended by ADK):
```bash
# On Mac/Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows (PowerShell):
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

---

### Step 5.2 — Create Your Project Folder

```bash
# Create the project
mkdir tracefly
cd tracefly

# Create a virtual environment (keeps your packages isolated)
uv venv --python 3.11
source .venv/bin/activate   # Mac/Linux
# OR on Windows:
.venv\Scripts\activate
```

You'll see `(tracefly)` or `(.venv)` appear before your terminal prompt. This means you're in the virtual environment. Always activate this before working on the project.

---

### Step 5.3 — Create requirements.txt

Create a file called `requirements.txt` in the `tracefly/` folder with exactly this content:

```
google-adk>=2.0.0
litellm>=1.40.0
anthropic>=0.30.0
psycopg2-binary>=2.9.0
sentence-transformers>=3.0.0
hdbscan>=0.8.38
numpy>=1.26.0
python-dotenv>=1.0.0
requests>=2.32.0
datasets>=2.20.0
```

Install everything:
```bash
uv pip install -r requirements.txt
```

This will take 3–5 minutes the first time.

---

### Step 5.4 — Install Docker Desktop and Start the Database

**What is Docker?** Think of it as a way to run a mini-server (Postgres) on your laptop without installing it properly. When you're done, you just stop it. It leaves no trace on your system.

1. Go to **docker.com/products/docker-desktop** and download Docker Desktop (free)
2. Install it and open it — you'll see a whale icon in your menu bar
3. You don't need to create an account

Create `docker-compose.yml` in your `tracefly/` folder:

```yaml
version: '3.8'

services:
  db:
    image: pgvector/pgvector:pg16      # Postgres 16 with pgvector already installed
    container_name: tracefly_db
    environment:
      POSTGRES_DB: tracefly
      POSTGRES_USER: tracefly
      POSTGRES_PASSWORD: tracefly_local
    ports:
      - "5432:5432"                    # Postgres is available on your machine at port 5432
    volumes:
      - tracefly_data:/var/lib/postgresql/data   # data persists when you restart

volumes:
  tracefly_data:
```

Start the database:
```bash
docker-compose up -d
```

The `-d` means "run in background". You'll see Docker pull the image (first time only, ~200MB) and start the container. After 10 seconds, Postgres is running.

Check it started:
```bash
docker-compose ps
```

You should see `tracefly_db` with status `Up`.

**To stop the database when you're done working:**
```bash
docker-compose down
```

**Your data is safe** — it's stored in the `tracefly_data` volume and survives restarts.

---

### Step 5.5 — Create Your .env File

Create a file called `.env` in the `tracefly/` folder:

```
# Anthropic — your only real secret
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Database — points at Docker Postgres running on your machine
DATABASE_URL=postgresql://tracefly:tracefly_local@localhost:5432/tracefly

# Slack (optional — leave blank to just print digests to terminal)
SLACK_WEBHOOK_URL=

# TraceFly config
EMBEDDING_MODEL=all-MiniLM-L6-v2
CLUSTER_MIN_SIZE=5
```

Also create `.env.example` — this is the file you commit to GitHub so others know what to fill in:

```
# Anthropic
ANTHROPIC_API_KEY=your-anthropic-key-here

# Database (Docker default — works out of the box with docker-compose up)
DATABASE_URL=postgresql://tracefly:tracefly_local@localhost:5432/tracefly

# Slack (optional)
SLACK_WEBHOOK_URL=

# TraceFly config
EMBEDDING_MODEL=all-MiniLM-L6-v2
CLUSTER_MIN_SIZE=5
```

Create `.gitignore`:
```
.env
.venv/
__pycache__/
*.pyc
.DS_Store
```

**Note for Supabase users:** If you ever want to use Supabase instead of Docker, just replace the `DATABASE_URL` line with your Supabase connection string. Nothing else changes.

---

### Step 5.6 — Verify Everything Works

Create a file called `test_setup.py`:

```python
import os
from dotenv import load_dotenv
load_dotenv()

# Test Anthropic connection
import anthropic
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=50,
    messages=[{"role": "user", "content": "Say 'TraceFly setup works!' and nothing else."}]
)
print("✅ Claude says:", message.content[0].text)

# Test database connection
import psycopg2
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cursor = conn.cursor()
cursor.execute("SELECT version();")
version = cursor.fetchone()[0]
conn.close()
print(f"✅ Postgres connected: {version[:40]}...")

print("\n🚀 Setup complete! Ready to build.")
```

Run it:
```bash
python test_setup.py
```

You should see both green checkmarks. If the database connection fails, make sure Docker is running (`docker-compose up -d`).

---

## 6. Phase 1 — Database Schema

**Goal:** Create all the tables TraceFly needs in Postgres.  
**Time:** Half a day.

---

### Understanding What We're Storing

Think of the database as having four "notebooks":

1. **traces** — Every agent interaction, raw and then enriched
2. **clusters** — Groups of similar failures that TraceFly discovered
3. **proposals** — Prompt change suggestions for each cluster
4. **digests** — History of summaries that were sent

---

### Step 6.1 — Create the Schema File

Create `database/schema.sql`:

```sql
-- Enable the vector extension (you already did this in the Supabase dashboard,
-- but this makes it explicit)
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- TABLE 1: traces
-- Stores every agent interaction
-- ============================================================
CREATE TABLE IF NOT EXISTS traces (
    -- Identity
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id              TEXT UNIQUE NOT NULL,   -- your agent's run ID
    session_id            TEXT,                   -- groups multi-turn conversations
    created_at            TIMESTAMPTZ DEFAULT NOW(),

    -- What happened
    user_input            TEXT,                   -- what the user said/sent
    final_output          TEXT,                   -- what the agent replied
    agent_steps           JSONB,                  -- tool calls, intermediate steps
    prompt_version_id     TEXT,                   -- which prompt was used

    -- Technical details
    model_name            TEXT,                   -- e.g. "claude-sonnet-4-6"
    token_count           INTEGER,
    cost_usd              NUMERIC(10, 6),
    latency_ms            INTEGER,

    -- Outcome signals
    user_feedback         TEXT,                   -- "thumbs_up", "thumbs_down", null
    escalation_flag       BOOLEAN DEFAULT FALSE,  -- was this handed off to a human?
    
    -- Enrichment (filled in by the Enrichment Agent later)
    intent                TEXT,                   -- e.g. "returns_policy"
    outcome               TEXT,                   -- "success", "failure", "near_miss"
    error_mode            TEXT,                   -- "hallucination", "tool_misuse", etc.
    enriched_at           TIMESTAMPTZ,            -- when enrichment ran

    -- Clustering (filled in by Clustering Agent)
    cluster_id            UUID,                   -- which cluster this trace belongs to
    embedding             vector(384)             -- the semantic vector (384 dims for MiniLM)
);

-- Index for fast lookups by time and outcome
CREATE INDEX IF NOT EXISTS idx_traces_created ON traces(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_traces_outcome ON traces(outcome);
CREATE INDEX IF NOT EXISTS idx_traces_cluster ON traces(cluster_id);
CREATE INDEX IF NOT EXISTS idx_traces_enriched ON traces(enriched_at) 
    WHERE enriched_at IS NULL;  -- fast query for "unenriched traces"

-- Vector similarity index (HNSW is faster for search, IVFFlat for large scale)
CREATE INDEX IF NOT EXISTS idx_traces_embedding ON traces 
    USING hnsw (embedding vector_cosine_ops);


-- ============================================================
-- TABLE 2: clusters
-- Groups of similar traces
-- ============================================================
CREATE TABLE IF NOT EXISTS clusters (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    updated_at            TIMESTAMPTZ DEFAULT NOW(),

    -- What the cluster is
    description           TEXT,           -- LLM-generated human-readable summary
    dominant_intent       TEXT,           -- most common intent in cluster
    dominant_error_mode   TEXT,           -- most common error type
    
    -- Size and impact
    trace_count           INTEGER DEFAULT 0,
    affected_user_count   INTEGER DEFAULT 0,
    impact_score          NUMERIC(6, 2),  -- calculated score for prioritization
    severity_weight       NUMERIC(4, 2),  -- based on error mode type

    -- Status tracking
    status                TEXT DEFAULT 'open',  -- "open", "in_progress", "resolved"
    
    -- Trace references — full traceability back to source data
    representative_trace_ids   JSONB,      -- top 5 example trace IDs (for display)
    all_trace_ids              JSONB,      -- ALL trace IDs in this cluster (for full drill-down)

    -- Time window this cluster covers
    window_start          TIMESTAMPTZ,
    window_end            TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_clusters_impact ON clusters(impact_score DESC);
CREATE INDEX IF NOT EXISTS idx_clusters_status ON clusters(status);


-- ============================================================
-- TABLE 3: proposals
-- Prompt change suggestions generated for each cluster
-- ============================================================
CREATE TABLE IF NOT EXISTS proposals (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id            UUID REFERENCES clusters(id),
    created_at            TIMESTAMPTZ DEFAULT NOW(),

    -- The suggestion
    hypothesis            TEXT,           -- "This change will reduce X because Y"
    reasoning             TEXT,           -- WHY this specific change — root cause analysis
    change_type           TEXT,           -- "instruction_addition", "constraint", etc.
    prompt_before         TEXT,           -- the current prompt section
    prompt_after          TEXT,           -- the proposed new version
    target_metric         TEXT,           -- what metric this aims to improve
    risk_level            TEXT,           -- "low", "medium", "high"

    -- Confidence scoring (Claude self-assesses how certain it is)
    confidence_score      NUMERIC(3, 1),  -- 0.0 to 10.0
    confidence_explanation TEXT,          -- plain-English explanation of the score

    ranking_score         NUMERIC(4, 2),

    -- Review
    review_status         TEXT DEFAULT 'pending',  -- "pending", "accepted", "rejected"
    review_notes          TEXT,           -- why rejected, or implementation notes
    reviewed_at           TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_proposals_cluster ON proposals(cluster_id);
CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(review_status);
CREATE INDEX IF NOT EXISTS idx_proposals_confidence ON proposals(confidence_score DESC);


-- ============================================================
-- TABLE 4: digests
-- History of summaries sent
-- ============================================================
CREATE TABLE IF NOT EXISTS digests (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    content               TEXT,           -- the full digest text
    clusters_included     JSONB,          -- which cluster IDs were in this digest
    sent_to               TEXT            -- "slack", "terminal", "email"
);
```

---

### Step 6.2 — Run the Schema Against Docker Postgres

You have two options. Pick whichever feels easier.

**Option A — Run from terminal (recommended):**
```bash
# This pipes schema.sql directly into Postgres running in Docker
docker exec -i tracefly_db psql -U tracefly -d tracefly < database/schema.sql
```

You should see output like:
```
CREATE EXTENSION
CREATE TABLE
CREATE INDEX
CREATE TABLE
CREATE TABLE
CREATE TABLE
```

**Option B — Use a visual tool:**  
Download **TablePlus** (free tier, Mac/Windows/Linux) from tableplus.com. Connect with:
- Host: `localhost`
- Port: `5432`
- Database: `tracefly`
- User: `tracefly`
- Password: `tracefly_local`

Then paste and run the SQL from `schema.sql` in the query editor. You'll see your four tables appear in the left sidebar.

---

### Step 6.3 — Create a Python Database Helper

Create `database/__init__.py` (empty file).

Create `database/db.py`:

```python
"""
Simple helper to connect to Postgres (Docker locally, or any Postgres via DATABASE_URL).
We import this in every tool that needs the database.
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    """
    Returns a Postgres connection.
    Reads DATABASE_URL from .env — works with Docker locally
    or any Postgres (Supabase, Neon, RDS) by just changing that one variable.
    """
    return psycopg2.connect(os.environ["DATABASE_URL"])
```

**Why just one connection method now?** We removed the Supabase client since we're using Docker. All database operations use standard psycopg2, which works identically against any Postgres — local Docker, Supabase, or anything else.

---

## 7. Phase 2 — Trace Capture SDK

**Goal:** A simple Python function that records agent interactions to Supabase.  
**Time:** 1–2 days.

This is the most important piece because without traces, nothing else works. But it's also the simplest code in the whole project — no agents, no LLMs, just a function that saves data.

---

### Understanding What We're Capturing

Every time your agent runs, we want to save:
- What the user asked
- What the agent replied
- What tools it used along the way
- How long it took
- How many tokens it used

---

### Step 7.1 — Create the Capture Module

Create `sdk/__init__.py` (empty file).

Create `sdk/capture.py`:

```python
"""
TraceFly SDK — Trace Capture

This is the ONLY file you need to add to your existing agent.
Usage in your agent:
    from tracefly.sdk.capture import capture_trace
    
    result = your_agent_run(user_input)
    capture_trace(
        user_input=user_input,
        final_output=result,
        model_name="claude-sonnet-4-6",
        prompt_version_id="v1.0"
    )
"""
import uuid
import time
import json
from datetime import datetime, timezone
from typing import Optional
from database.db import get_db_connection


def capture_trace(
    user_input: str,
    final_output: str,
    model_name: str,
    prompt_version_id: str = "unknown",
    session_id: Optional[str] = None,
    agent_steps: Optional[list] = None,
    token_count: Optional[int] = None,
    cost_usd: Optional[float] = None,
    latency_ms: Optional[int] = None,
    user_feedback: Optional[str] = None,
    escalation_flag: bool = False,
) -> str:
    """
    Records one agent interaction to the TraceFly database.
    
    Call this once after every agent run completes.
    
    Returns the trace_id so you can update it later (e.g., with user feedback).
    """
    
    trace_id = str(uuid.uuid4())
    
    # Mask PII — basic version. Extend this regex list for your use case.
    user_input_masked = _mask_pii(user_input)
    final_output_masked = _mask_pii(final_output)
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO traces (
                trace_id, session_id, user_input, final_output,
                agent_steps, prompt_version_id, model_name,
                token_count, cost_usd, latency_ms,
                user_feedback, escalation_flag
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            trace_id,
            session_id or str(uuid.uuid4()),
            user_input_masked,
            final_output_masked,
            json.dumps(agent_steps or []),
            prompt_version_id,
            model_name,
            token_count,
            cost_usd,
            latency_ms,
            user_feedback,
            escalation_flag
        ))
        conn.commit()
        print(f"[TraceFly] Trace captured: {trace_id}")
        return trace_id
    except Exception as e:
        print(f"[TraceFly] Warning: Failed to capture trace: {e}")
        return trace_id  # Don't crash your agent if TraceFly fails
    finally:
        cursor.close()
        conn.close()


def update_feedback(trace_id: str, feedback: str) -> None:
    """
    Call this after you receive user feedback (thumbs up/down).
    feedback should be: "thumbs_up", "thumbs_down", or "escalated"
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE traces 
            SET user_feedback = %s,
                escalation_flag = %s
            WHERE trace_id = %s
        """, (
            feedback,
            feedback == "escalated",
            trace_id
        ))
        conn.commit()
    except Exception as e:
        print(f"[TraceFly] Warning: Failed to update feedback: {e}")
    finally:
        cursor.close()
        conn.close()


def _mask_pii(text: str) -> str:
    """
    Basic PII masking. Replace with NER-based masking for production.
    This catches the most common patterns.
    """
    import re
    
    # Email addresses
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                  '[EMAIL]', text)
    
    # Phone numbers (basic international format)
    text = re.sub(r'\b(\+?[\d\s\-\(\)]{7,15})\b', '[PHONE]', text)
    
    # Credit card patterns (16 digits)
    text = re.sub(r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b',
                  '[CARD]', text)
    
    return text
```

---

### Step 7.2 — Create a Timing Helper (Optional but Useful)

Add to `sdk/capture.py` at the bottom — a context manager that automatically measures latency:

```python
from contextlib import contextmanager

@contextmanager
def trace_timer():
    """
    Use this to automatically measure how long your agent takes.
    
    Usage:
        with trace_timer() as timer:
            result = your_agent_run(user_input)
        latency = timer.latency_ms
    """
    start = time.time()
    
    class Timer:
        latency_ms = None
    
    t = Timer()
    try:
        yield t
    finally:
        t.latency_ms = int((time.time() - start) * 1000)
```

---

### Step 7.3 — How to Add TraceFly to YOUR Agent

This is the most important step for you as a builder. Here is what adding TraceFly to any agent looks like:

**Before TraceFly (your existing agent code):**
```python
# Your existing agent
response = my_agent.run(user_message)
print(response)
```

**After adding TraceFly (you add 5 lines):**
```python
import time
from sdk.capture import capture_trace, trace_timer

# Your existing agent — UNCHANGED
with trace_timer() as timer:
    response = my_agent.run(user_message)

# Add this after your agent runs
capture_trace(
    user_input=user_message,
    final_output=str(response),
    model_name="claude-sonnet-4-6",
    prompt_version_id="v1.0",
    latency_ms=timer.latency_ms
)

print(response)
```

That's it. Your agent behaviour is unchanged. TraceFly silently records what happened.

---

### Step 7.4 — Test the Capture

Create `test_capture.py`:

```python
from sdk.capture import capture_trace

# Simulate an agent trace
trace_id = capture_trace(
    user_input="How do I return my order from Germany?",
    final_output="You can return your order within 14 days. Visit returns.example.com",
    model_name="claude-sonnet-4-6",
    prompt_version_id="v1.0",
    token_count=250,
    cost_usd=0.003,
    latency_ms=1240,
)
print(f"Trace saved with ID: {trace_id}")

# Add a few more test traces
for i in range(5):
    capture_trace(
        user_input=f"Test question {i}: What is your return policy?",
        final_output=f"Test answer {i}: Our return policy is 30 days.",
        model_name="claude-sonnet-4-6",
        prompt_version_id="v1.0",
    )

print("Test traces saved. Check your Supabase dashboard!")
```

Run it:
```bash
python test_capture.py
```

Go to your Supabase dashboard → Table Editor → `traces`. You should see 6 rows.

---

## 8. Phase 3 — Enrichment Agent

**Goal:** An ADK agent with a tool that reads unenriched traces and adds intent, outcome, and error mode labels.  
**Time:** 2–3 days.

This is where you write your first real ADK tool. The pattern you learn here is the same pattern used by all four tools.

---

### Understanding What Enrichment Does

Raw trace in the database:
```
user_input: "How do I return my order?"
final_output: "You can return within 30 days."
intent: NULL          ← empty, needs to be filled
outcome: NULL         ← empty, needs to be filled
error_mode: NULL      ← empty, needs to be filled
```

After enrichment:
```
user_input: "How do I return my order?"
final_output: "You can return within 30 days."
intent: "returns_policy"
outcome: "success"
error_mode: null
enriched_at: 2026-06-26 09:00:00
```

The enrichment tool uses Claude (via the Anthropic API) to classify the intent, and rules to classify the outcome.

---

### Step 8.1 — Create the Enrichment Tool

Create `tracefly_agent/tools/__init__.py` (empty file).

Create `tracefly_agent/tools/enrich.py`:

```python
"""
Tool 1: enrich_traces

Reads unenriched traces from the database and adds:
- intent: what the user was trying to do
- outcome: did the agent succeed?  
- error_mode: what type of failure (if any)?
- embedding: a vector representation for clustering later
"""
import json
from datetime import datetime, timezone
from sentence_transformers import SentenceTransformer
from database.db import get_db_connection
import anthropic
import os

# Load the embedding model once (it's loaded into memory the first time)
# all-MiniLM-L6-v2 is small, fast, free, and good enough for clustering
_embedding_model = None

def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        print("[Enrich] Loading embedding model...")
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


def enrich_traces(batch_size: int = 50) -> dict:
    """
    Enriches the next batch of unenriched traces.
    
    This is an ADK tool — it must return a dict with a "status" key.
    ADK will pass the result to Claude, which decides what to do next.
    
    Args:
        batch_size: How many traces to process in one call (default 50)
    
    Returns:
        dict with status and summary of what was done
    """
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Step 1: Get unenriched traces
        cursor.execute("""
            SELECT id, trace_id, user_input, final_output, 
                   user_feedback, escalation_flag, agent_steps
            FROM traces
            WHERE enriched_at IS NULL
            ORDER BY created_at ASC
            LIMIT %s
        """, (batch_size,))
        
        rows = cursor.fetchall()
        
        if not rows:
            return {
                "status": "success",
                "message": "No unenriched traces found. All caught up!",
                "processed": 0
            }
        
        print(f"[Enrich] Processing {len(rows)} traces...")
        
        # Set up Claude client
        claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        embedding_model = _get_embedding_model()
        
        processed = 0
        errors = 0
        
        for row in rows:
            trace_db_id, trace_id, user_input, final_output, \
                user_feedback, escalation_flag, agent_steps_json = row
            
            try:
                # Step 2: Classify intent using Claude
                intent = _classify_intent(claude, user_input, final_output)
                
                # Step 3: Classify outcome using rules (fast, no LLM needed)
                outcome = _classify_outcome(user_feedback, escalation_flag)
                
                # Step 4: Classify error mode
                error_mode = _classify_error_mode(
                    claude, user_input, final_output, 
                    outcome, agent_steps_json
                )
                
                # Step 5: Generate embedding for clustering
                # We embed the combination of intent + user_input + outcome
                text_to_embed = f"{intent} {user_input[:200]} {outcome}"
                embedding = embedding_model.encode(text_to_embed).tolist()
                
                # Step 6: Save enrichment back to database
                cursor.execute("""
                    UPDATE traces
                    SET intent = %s,
                        outcome = %s,
                        error_mode = %s,
                        embedding = %s::vector,
                        enriched_at = %s
                    WHERE id = %s
                """, (
                    intent,
                    outcome,
                    error_mode,
                    str(embedding),  # pgvector expects a string like "[0.1, 0.2, ...]"
                    datetime.now(timezone.utc),
                    trace_db_id
                ))
                
                processed += 1
                
            except Exception as e:
                print(f"[Enrich] Error on trace {trace_id}: {e}")
                errors += 1
                # Mark as enriched with error so we don't retry infinitely
                cursor.execute("""
                    UPDATE traces SET enriched_at = %s WHERE id = %s
                """, (datetime.now(timezone.utc), trace_db_id))
        
        conn.commit()
        
        return {
            "status": "success",
            "processed": processed,
            "errors": errors,
            "message": f"Enriched {processed} traces. {errors} errors."
        }
    
    except Exception as e:
        conn.rollback()
        return {
            "status": "error",
            "message": f"Enrichment failed: {str(e)}"
        }
    finally:
        cursor.close()
        conn.close()


def _classify_intent(claude, user_input: str, final_output: str) -> str:
    """
    Uses Claude to classify what the user was trying to do.
    
    IMPORTANT: For your real deployment, replace the intent list below
    with the actual intents in YOUR agent's domain.
    """
    
    response = claude.messages.create(
        model="claude-haiku-4-5-20251001",  # Cheaper model for simple classification
        max_tokens=50,
        messages=[{
            "role": "user",
            "content": f"""Classify this agent interaction into exactly ONE intent label.

User said: {user_input[:500]}
Agent replied: {final_output[:500]}

Choose the single best label from this list:
- returns_policy
- product_question  
- payment_issue
- account_management
- complaint
- general_inquiry
- technical_support
- other

Reply with ONLY the label, nothing else."""
        }]
    )
    
    intent = response.content[0].text.strip().lower()
    
    # Validate the response is one of our known intents
    valid_intents = [
        "returns_policy", "product_question", "payment_issue",
        "account_management", "complaint", "general_inquiry",
        "technical_support", "other"
    ]
    return intent if intent in valid_intents else "other"


def _classify_outcome(user_feedback: str, escalation_flag: bool) -> str:
    """
    Rules-based outcome classification. Fast, no LLM needed.
    
    Priority order:
    1. Explicit thumbs down → failure
    2. Escalation → failure  
    3. Explicit thumbs up → success
    4. No signal → near_miss (we don't know)
    """
    if user_feedback == "thumbs_down":
        return "failure"
    if escalation_flag:
        return "failure"
    if user_feedback == "thumbs_up":
        return "success"
    return "near_miss"


def _classify_error_mode(claude, user_input: str, final_output: str, 
                          outcome: str, agent_steps_json) -> str:
    """
    Classifies what TYPE of failure occurred (only for failures).
    For successes, returns None.
    """
    
    if outcome == "success":
        return None
    
    # Check for loops first (no LLM needed — just count tool calls)
    if agent_steps_json:
        steps = json.loads(agent_steps_json) if isinstance(agent_steps_json, str) \
                else agent_steps_json
        tool_names = [s.get("tool") for s in steps if s.get("tool")]
        if len(tool_names) > 3 and len(set(tool_names)) < len(tool_names) / 2:
            return "loop"
    
    # For other failures, use Claude to classify
    response = claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=30,
        messages=[{
            "role": "user",
            "content": f"""What type of AI agent failure is this?

User asked: {user_input[:300]}
Agent answered: {final_output[:300]}

Choose ONE:
- hallucination (agent stated false facts)
- retrieval_miss (agent lacked needed information)
- tool_misuse (agent used wrong tool or wrong parameters)
- ux_confusion (agent response was unclear or confusing)
- safety_violation (agent violated a policy or safety rule)
- other_failure

Reply with ONLY the label."""
        }]
    )
    
    error_mode = response.content[0].text.strip().lower()
    valid_modes = [
        "hallucination", "retrieval_miss", "tool_misuse",
        "ux_confusion", "safety_violation", "other_failure"
    ]
    return error_mode if error_mode in valid_modes else "other_failure"
```

---

## 9. Phase 4 — Clustering Agent

**Goal:** A tool that groups enriched traces into meaningful failure clusters.  
**Time:** 2–3 days.

---

### Understanding Clustering Without Math Jargon

Imagine you have 1,000 failure traces. You could read all 1,000 — but that's impossible. Clustering automatically groups them so you might end up with:

- **Cluster A (150 traces):** EU customers asking about return costs who got wrong answers
- **Cluster B (80 traces):** Payment flow where the agent looped 4+ times
- **Cluster C (200 traces):** Product questions where the agent gave outdated info

Instead of reading 1,000 traces, you read 3 cluster summaries and immediately know where the problems are.

**How clustering works (simplified):**
1. Every trace gets turned into a list of numbers (the "embedding" we computed in enrichment) that captures its meaning
2. Traces with similar meanings end up as similar lists of numbers
3. The clustering algorithm (HDBSCAN) finds dense groups of similar traces
4. Claude generates a human-readable summary of each group

---

### Step 9.1 — Create the Clustering Tool

Create `tracefly_agent/tools/cluster.py`:

```python
"""
Tool 2: cluster_traces

Groups enriched failure traces into meaningful clusters using:
1. Embeddings (already computed during enrichment)
2. HDBSCAN clustering algorithm
3. Claude for generating human-readable cluster summaries
"""
import json
import numpy as np
from datetime import datetime, timezone, timedelta
import hdbscan
import anthropic
import os
from database.db import get_db_connection


def cluster_traces(days_back: int = 7, min_cluster_size: int = 5) -> dict:
    """
    Clusters failure and near-miss traces from the past N days.
    
    Args:
        days_back: How many days of traces to cluster (default 7)
        min_cluster_size: Minimum traces to form a cluster (default 5)
    
    Returns:
        dict with status and list of clusters found
    """
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Step 1: Get enriched failure/near-miss traces with embeddings
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        
        cursor.execute("""
            SELECT id, trace_id, user_input, final_output, 
                   intent, error_mode, outcome,
                   embedding::text
            FROM traces
            WHERE enriched_at IS NOT NULL
              AND outcome IN ('failure', 'near_miss')
              AND embedding IS NOT NULL
              AND created_at >= %s
            ORDER BY created_at DESC
        """, (cutoff,))
        
        rows = cursor.fetchall()
        
        if len(rows) < min_cluster_size:
            return {
                "status": "success",
                "message": f"Only {len(rows)} traces found. Need at least {min_cluster_size} to cluster.",
                "clusters_found": 0
            }
        
        print(f"[Cluster] Clustering {len(rows)} traces...")
        
        # Step 2: Extract embeddings into a numpy array
        trace_ids = []
        trace_data = []
        embeddings = []
        
        for row in rows:
            db_id, trace_id, user_input, final_output, \
                intent, error_mode, outcome, embedding_str = row
            
            # Parse the embedding string back into a list of floats
            embedding = json.loads(embedding_str)
            
            trace_ids.append(db_id)
            trace_data.append({
                "trace_id": trace_id,
                "user_input": user_input,
                "final_output": final_output,
                "intent": intent,
                "error_mode": error_mode,
                "outcome": outcome
            })
            embeddings.append(embedding)
        
        embedding_matrix = np.array(embeddings)
        
        # Step 3: Run HDBSCAN clustering
        # min_cluster_size: minimum number of traces to form a cluster
        # metric: cosine distance works well for text embeddings
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            metric='euclidean',  # We use euclidean on normalized vectors
            cluster_selection_method='eom'
        )
        
        # Normalize embeddings before clustering (improves cosine-like behavior)
        norms = np.linalg.norm(embedding_matrix, axis=1, keepdims=True)
        normalized = embedding_matrix / (norms + 1e-10)
        
        cluster_labels = clusterer.fit_predict(normalized)
        
        # cluster_labels is an array like: [0, 0, 1, -1, 0, 2, 1, ...]
        # -1 means "noise" (doesn't belong to any cluster) — we skip those
        unique_clusters = set(cluster_labels) - {-1}
        
        if not unique_clusters:
            return {
                "status": "success",
                "message": "No clusters found. Traces may be too diverse or too few.",
                "clusters_found": 0
            }
        
        print(f"[Cluster] Found {len(unique_clusters)} clusters")
        
        # Step 4: For each cluster, get representative traces and generate a summary
        claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        
        clusters_created = []
        
        for cluster_id in unique_clusters:
            # Get indices of traces in this cluster
            cluster_indices = [i for i, label in enumerate(cluster_labels) 
                               if label == cluster_id]
            
            cluster_traces_data = [trace_data[i] for i in cluster_indices]
            cluster_db_ids = [trace_ids[i] for i in cluster_indices]
            
            # Pick up to 5 representative traces (first 5 for MVP)
            representative = cluster_traces_data[:5]
            representative_ids = cluster_db_ids[:5]
            
            # Determine dominant intent and error mode
            intents = [t["intent"] for t in cluster_traces_data if t["intent"]]
            error_modes = [t["error_mode"] for t in cluster_traces_data if t["error_mode"]]
            
            dominant_intent = _most_common(intents) or "unknown"
            dominant_error_mode = _most_common(error_modes) or "unknown"
            
            # Generate human-readable description using Claude
            description = _generate_cluster_description(
                claude, cluster_traces_data, dominant_intent, dominant_error_mode
            )
            
            # Save the cluster to the database
            # representative_trace_ids = top 5 shown in UI and used for suggestions
            # all_trace_ids = every trace in this cluster for full drill-down
            cluster_uuid = _save_cluster(
                cursor, conn,
                description=description,
                dominant_intent=dominant_intent,
                dominant_error_mode=dominant_error_mode,
                trace_count=len(cluster_indices),
                representative_trace_ids=representative_ids,
                all_trace_ids=cluster_db_ids,       # full list — all N traces
                window_start=cutoff,
                window_end=datetime.now(timezone.utc)
            )
            
            # Update the cluster_id on all traces in this cluster
            cursor.execute("""
                UPDATE traces SET cluster_id = %s
                WHERE id = ANY(%s::uuid[])
            """, (cluster_uuid, cluster_db_ids))
            
            conn.commit()
            
            clusters_created.append({
                "cluster_id": str(cluster_uuid),
                "description": description[:100] + "...",
                "trace_count": len(cluster_indices),
                "dominant_intent": dominant_intent,
                "dominant_error_mode": dominant_error_mode
            })
        
        return {
            "status": "success",
            "clusters_found": len(clusters_created),
            "clusters": clusters_created,
            "message": f"Created {len(clusters_created)} clusters from {len(rows)} traces."
        }
    
    except Exception as e:
        conn.rollback()
        return {
            "status": "error",
            "message": f"Clustering failed: {str(e)}"
        }
    finally:
        cursor.close()
        conn.close()


def _most_common(lst: list):
    """Returns the most common element in a list."""
    if not lst:
        return None
    return max(set(lst), key=lst.count)


def _generate_cluster_description(claude, traces: list, intent: str, error_mode: str) -> str:
    """Asks Claude to write a human-readable cluster summary."""
    
    # Build examples from the first 3 traces
    examples = ""
    for i, t in enumerate(traces[:3]):
        examples += f"\nExample {i+1}:\n"
        examples += f"  User: {t['user_input'][:200]}\n"
        examples += f"  Agent: {t['final_output'][:200]}\n"
    
    response = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": f"""You are analyzing a cluster of AI agent failures.

Dominant intent: {intent}
Dominant error type: {error_mode}
Number of affected interactions: {len(traces)}

Example failures:
{examples}

Write a 2-3 sentence description of what goes wrong in this cluster.
Be specific about WHAT the agent gets wrong and WHY it matters.
Do not use jargon. Write as if explaining to a product manager.
Do not include any preamble, just the description."""
        }]
    )
    
    return response.content[0].text.strip()


def _save_cluster(cursor, conn, **kwargs) -> str:
    """Saves a cluster to the database and returns its UUID.
    
    Stores both representative_trace_ids (top 5 for display) and
    all_trace_ids (every trace in the cluster for full traceability).
    This means you can always drill from a cluster back to every
    individual source trace that contributed to it.
    """
    import uuid
    
    cluster_uuid = str(uuid.uuid4())
    
    cursor.execute("""
        INSERT INTO clusters (
            id, description, dominant_intent, dominant_error_mode,
            trace_count, representative_trace_ids, all_trace_ids,
            window_start, window_end
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        cluster_uuid,
        kwargs["description"],
        kwargs["dominant_intent"],
        kwargs["dominant_error_mode"],
        kwargs["trace_count"],
        json.dumps([str(id) for id in kwargs["representative_trace_ids"]]),
        json.dumps([str(id) for id in kwargs["all_trace_ids"]]),
        kwargs["window_start"],
        kwargs["window_end"]
    ))
    
    return cursor.fetchone()[0]
```

---

## 10. Phase 5 — Suggestion Agent

**Goal:** A tool that reads clusters and generates prompt improvement proposals.  
**Time:** 2–3 days.

---

### Step 10.1 — Create the Scoring Tool

Create `tracefly_agent/tools/score.py`:

```python
"""
Tool 3: score_clusters

Calculates impact scores for each cluster and ranks them.
This tells you WHICH cluster to fix first.
"""
from database.db import get_db_connection


# Severity weights by error type — how bad is each failure mode?
SEVERITY_WEIGHTS = {
    "safety_violation": 10,   # Highest: regulatory/brand risk
    "hallucination": 8,       # High: damages trust directly
    "tool_misuse": 7,         # High: can cause wrong actions
    "retrieval_miss": 5,      # Medium: reduces helpfulness
    "ux_confusion": 4,        # Medium: drives abandonment
    "loop": 4,                # Medium: wastes cost
    "other_failure": 3,       # Lower: catch-all
    "unknown": 2,
}


def score_clusters() -> dict:
    """
    Calculates impact scores for all clusters and updates the database.
    
    Impact score formula:
        impact_score = trace_count × severity_weight
    
    (In Phase 2 we'll add business event data to make this richer)
    """
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, trace_count, dominant_error_mode
            FROM clusters
            WHERE status = 'open'
        """)
        
        clusters = cursor.fetchall()
        
        if not clusters:
            return {
                "status": "success",
                "message": "No open clusters to score.",
                "scored": 0
            }
        
        scored = 0
        for cluster_id, trace_count, error_mode in clusters:
            severity = SEVERITY_WEIGHTS.get(error_mode or "unknown", 2)
            impact_score = trace_count * severity
            
            cursor.execute("""
                UPDATE clusters
                SET impact_score = %s, severity_weight = %s
                WHERE id = %s
            """, (impact_score, severity, cluster_id))
            
            scored += 1
        
        conn.commit()
        
        # Return the top 5 clusters for Claude to see
        cursor.execute("""
            SELECT id, description, dominant_intent, dominant_error_mode,
                   trace_count, impact_score
            FROM clusters
            WHERE status = 'open'
            ORDER BY impact_score DESC
            LIMIT 5
        """)
        
        top_clusters = []
        for row in cursor.fetchall():
            top_clusters.append({
                "cluster_id": str(row[0]),
                "description": row[1][:100] + "..." if row[1] else "",
                "intent": row[2],
                "error_mode": row[3],
                "trace_count": row[4],
                "impact_score": float(row[5]) if row[5] else 0
            })
        
        return {
            "status": "success",
            "scored": scored,
            "top_clusters": top_clusters,
            "message": f"Scored {scored} clusters. Top cluster has impact score {top_clusters[0]['impact_score'] if top_clusters else 0}."
        }
    
    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        cursor.close()
        conn.close()
```

---

### Step 10.2 — Create the Suggestion Tool

Create `tracefly_agent/tools/suggest.py`:

```python
"""
Tool 4: generate_suggestions

For the top N clusters, generates concrete prompt change proposals.

Each proposal includes:
- hypothesis       : what we're changing and why (one sentence)
- reasoning        : root cause analysis — why this specific failure happened
- prompt_before    : the current (broken) prompt section
- prompt_after     : the proposed fix
- confidence_score : how certain Claude is this will help (0–10)
- confidence_explanation : plain-English explanation of the score

The reasoning and confidence score are what make proposals trustworthy
and actionable — a PM can read them and decide whether to implement
without needing to dig into the raw traces themselves.
"""
import json
import uuid
import anthropic
import os
from database.db import get_db_connection


def generate_suggestions(top_n: int = 3) -> dict:
    """
    Generates prompt improvement proposals for the top N clusters.
    
    Args:
        top_n: How many clusters to generate suggestions for (default 3)
    
    Returns:
        dict with generated proposals including confidence scores
    """
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get the top clusters by impact score
        cursor.execute("""
            SELECT c.id, c.description, c.dominant_intent, 
                   c.dominant_error_mode, c.trace_count,
                   c.representative_trace_ids, c.impact_score
            FROM clusters c
            WHERE c.status = 'open'
              AND c.impact_score IS NOT NULL
            ORDER BY c.impact_score DESC
            LIMIT %s
        """, (top_n,))
        
        clusters = cursor.fetchall()
        
        if not clusters:
            return {
                "status": "success",
                "message": "No scored clusters to generate suggestions for.",
                "proposals_created": 0
            }
        
        claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        proposals_created = 0
        all_proposals = []
        
        for cluster_row in clusters:
            cluster_id, description, intent, error_mode, \
                trace_count, rep_trace_ids_json, impact_score = cluster_row
            
            # Get representative failure AND success traces
            # Having both gives Claude contrast — what worked vs what didn't
            rep_ids = json.loads(rep_trace_ids_json) if rep_trace_ids_json else []
            failure_examples = _get_trace_examples(cursor, rep_ids, outcome="failure")
            success_examples = _get_trace_examples_by_intent(
                cursor, intent, outcome="success", limit=2
            )
            
            # Generate 2 proposals per cluster
            proposals = _generate_proposals_for_cluster(
                claude,
                description=description,
                intent=intent,
                error_mode=error_mode,
                failure_examples=failure_examples,
                success_examples=success_examples,
                trace_count=trace_count,
                impact_score=impact_score
            )
            
            # Save proposals to database
            for proposal in proposals:
                cursor.execute("""
                    INSERT INTO proposals (
                        id, cluster_id, hypothesis, reasoning,
                        change_type, prompt_before, prompt_after,
                        target_metric, risk_level,
                        confidence_score, confidence_explanation,
                        ranking_score
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    str(uuid.uuid4()),
                    cluster_id,
                    proposal.get("hypothesis", ""),
                    proposal.get("reasoning", ""),
                    proposal.get("change_type", ""),
                    proposal.get("prompt_before", ""),
                    proposal.get("prompt_after", ""),
                    proposal.get("target_metric", ""),
                    proposal.get("risk_level", "medium"),
                    proposal.get("confidence_score", 5.0),
                    proposal.get("confidence_explanation", ""),
                    proposal.get("confidence_score", 5.0)  # ranking_score = confidence for now
                ))
                proposals_created += 1
                all_proposals.append({
                    "cluster": description[:80] + "...",
                    "hypothesis": proposal.get("hypothesis", "")[:100] + "...",
                    "confidence_score": proposal.get("confidence_score"),
                })
        
        conn.commit()
        
        return {
            "status": "success",
            "proposals_created": proposals_created,
            "proposals": all_proposals,
            "message": (
                f"Generated {proposals_created} proposals for {len(clusters)} clusters. "
                f"Confidence scores range from "
                f"{min(p['confidence_score'] for p in all_proposals if p['confidence_score']):.1f} "
                f"to "
                f"{max(p['confidence_score'] for p in all_proposals if p['confidence_score']):.1f}."
            )
        }
    
    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        cursor.close()
        conn.close()


def _get_trace_examples(cursor, trace_ids: list, outcome: str = "failure") -> list:
    """Fetches specific traces by ID, filtered by outcome."""
    if not trace_ids:
        return []
    
    cursor.execute("""
        SELECT user_input, final_output, error_mode, intent
        FROM traces
        WHERE id = ANY(%s::uuid[])
          AND outcome = %s
        LIMIT 5
    """, (trace_ids, outcome))
    
    return [
        {
            "user_input": r[0],
            "final_output": r[1],
            "error_mode": r[2],
            "intent": r[3]
        }
        for r in cursor.fetchall()
    ]


def _get_trace_examples_by_intent(cursor, intent: str,
                                   outcome: str = "success", limit: int = 2) -> list:
    """
    Fetches success traces for the same intent.
    These give Claude a contrast — what a GOOD response looks like
    vs the failures, making suggestions more targeted.
    """
    cursor.execute("""
        SELECT user_input, final_output
        FROM traces
        WHERE intent = %s
          AND outcome = %s
        ORDER BY RANDOM()
        LIMIT %s
    """, (intent, outcome, limit))
    
    return [{"user_input": r[0], "final_output": r[1]} for r in cursor.fetchall()]


def _generate_proposals_for_cluster(
    claude,
    description: str,
    intent: str,
    error_mode: str,
    failure_examples: list,
    success_examples: list,
    trace_count: int,
    impact_score: float
) -> list:
    """
    Asks Claude to generate 2 structured prompt change proposals with
    full reasoning and confidence scoring.
    
    We pass both failure AND success examples so Claude can contrast
    what went wrong vs what worked, leading to more precise proposals.
    """
    
    # Format failure examples
    failures_text = ""
    for i, ex in enumerate(failure_examples[:3]):
        failures_text += f"\nFAILURE {i+1} (error_mode: {ex.get('error_mode', 'unknown')}):\n"
        failures_text += f"  User asked: {ex['user_input'][:250]}\n"
        failures_text += f"  Agent replied (incorrectly): {ex['final_output'][:250]}\n"
    
    # Format success examples for contrast
    successes_text = ""
    if success_examples:
        successes_text = "\nEXAMPLES OF CORRECT RESPONSES (same intent, different outcome):\n"
        for i, ex in enumerate(success_examples):
            successes_text += f"\nSUCCESS {i+1}:\n"
            successes_text += f"  User asked: {ex['user_input'][:200]}\n"
            successes_text += f"  Agent replied (correctly): {ex['final_output'][:200]}\n"
    else:
        successes_text = "\n(No success examples available for this intent yet.)\n"
    
    response = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2500,
        messages=[{
            "role": "user",
            "content": f"""You are an expert at diagnosing and fixing AI agent prompt failures.

Your job is to analyse a cluster of failures and propose exactly 2 concrete prompt improvements.
For each proposal you must provide:
1. A clear hypothesis (what you're changing)
2. A detailed reasoning (WHY this failure happened and why your fix addresses the root cause)
3. A before/after prompt diff (literal text)
4. A confidence score with explanation (how certain are you this will actually help)

═══════════════════════════════════════════
FAILURE CLUSTER SUMMARY
═══════════════════════════════════════════
Description: {description}
Intent category: {intent}
Dominant error type: {error_mode}
Number of affected interactions: {trace_count}
Impact score: {impact_score}

═══════════════════════════════════════════
FAILURE EXAMPLES (what the agent got wrong)
═══════════════════════════════════════════
{failures_text}

═══════════════════════════════════════════
SUCCESS EXAMPLES (what good looks like)
═══════════════════════════════════════════
{successes_text}

═══════════════════════════════════════════
INSTRUCTIONS
═══════════════════════════════════════════
Respond with ONLY a valid JSON array — no preamble, no markdown fences.

The confidence_score field (0.0 to 10.0) should reflect:
- 9-10: The failure pattern is completely clear and the fix directly targets the root cause
- 7-8:  Good evidence, but the fix touches multiple behaviours — some monitoring needed
- 5-6:  Hypothesis is plausible but the root cause could be elsewhere (e.g. retrieval, not prompt)
- 3-4:  Uncertain — more investigation recommended before implementing
- 1-2:  Very speculative — do not implement without further analysis

[
  {{
    "hypothesis": "One clear sentence: what specific change you are proposing and what outcome you expect",
    "reasoning": "2-4 sentences explaining: (1) what root cause in the agent behaviour is causing these failures, (2) why this specific prompt change addresses that root cause, (3) what you expect will change after the fix. Be specific — reference the failure examples above.",
    "change_type": "one of: instruction_addition, constraint_addition, format_change, clarification_requirement, policy_reference",
    "prompt_before": "The exact current prompt section that is causing the problem. Use 'Not available — add explicit instruction here' if the issue is a missing instruction rather than a bad one.",
    "prompt_after": "Your improved replacement. This must be literal prompt text the developer can copy-paste.",
    "target_metric": "The primary metric this change will improve: hallucination_rate, escalation_rate, csat, task_success_rate, or ux_clarity",
    "risk_level": "low, medium, or high — based on how broadly the change affects the prompt",
    "confidence_score": 8.5,
    "confidence_explanation": "Plain-English explanation of this score. What makes you confident? What uncertainty remains? E.g. 'High confidence because all 12 failure examples show the same missing step. Score is not 10 because we cannot rule out a retrieval issue contributing.'"
  }},
  {{
    ...second proposal, targeting a different aspect of the same failure cluster...
  }}
]"""
        }]
    )
    
    # Parse the JSON response safely
    try:
        response_text = response.content[0].text.strip()
        
        # Strip markdown code fences if Claude added them despite instructions
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # Remove first line (```json or ```) and last line (```)
            response_text = "\n".join(lines[1:-1])
        
        proposals = json.loads(response_text)
        
        if not isinstance(proposals, list):
            print(f"[Suggest] Unexpected response format — got {type(proposals)}")
            return []
        
        # Validate and clamp confidence scores to 0–10
        for p in proposals:
            score = p.get("confidence_score", 5.0)
            p["confidence_score"] = round(max(0.0, min(10.0, float(score))), 1)
        
        return proposals
    
    except json.JSONDecodeError as e:
        print(f"[Suggest] Failed to parse proposals JSON: {e}")
        print(f"[Suggest] Raw response was: {response_text[:300]}...")
        return []
    except Exception as e:
        print(f"[Suggest] Unexpected error parsing proposals: {e}")
        return []
```

---

## 11. Phase 6 — Digest and Wiring It All Together

**Goal:** A digest tool that summarizes findings, and the main ADK agent that orchestrates all four tools.  
**Time:** 1–2 days.

---

### Step 11.1 — Create the Digest Tool

Create `tracefly_agent/tools/digest.py`:

```python
"""
Digest Tool: Generates a human-readable summary of TraceFly findings.
Prints to terminal in MVP. Can be extended to send to Slack.
"""
import os
import requests
from datetime import datetime
from database.db import get_db_connection


def send_digest() -> dict:
    """
    Generates and sends a digest of the current TraceFly findings.
    In MVP: prints to terminal. Set SLACK_WEBHOOK_URL to also send to Slack.
    """
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get top clusters
        cursor.execute("""
            SELECT description, dominant_intent, dominant_error_mode,
                   trace_count, impact_score, status
            FROM clusters
            WHERE status = 'open'
            ORDER BY impact_score DESC NULLS LAST
            LIMIT 5
        """)
        clusters = cursor.fetchall()
        
        # Get pending proposals with confidence scores
        cursor.execute("""
            SELECT p.hypothesis, p.confidence_score, p.confidence_explanation,
                   p.risk_level, c.dominant_intent
            FROM proposals p
            JOIN clusters c ON p.cluster_id = c.id
            WHERE p.review_status = 'pending'
            ORDER BY p.confidence_score DESC NULLS LAST
            LIMIT 5
        """)
        top_proposals = cursor.fetchall()
        pending_proposals = len(top_proposals)
        
        # Get basic health metrics
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE outcome = 'success') as successes,
                COUNT(*) FILTER (WHERE outcome = 'failure') as failures,
                ROUND(AVG(latency_ms)) as avg_latency,
                ROUND(CAST(SUM(cost_usd) AS numeric), 4) as total_cost
            FROM traces
            WHERE created_at >= NOW() - INTERVAL '24 hours'
        """)
        health = cursor.fetchone()
        
        # Build the digest text
        digest = _format_digest(clusters, top_proposals, health)
        
        # Print to terminal always
        print("\n" + "="*60)
        print(digest)
        print("="*60 + "\n")
        
        # Send to Slack if configured
        slack_url = os.environ.get("SLACK_WEBHOOK_URL")
        if slack_url:
            _send_to_slack(slack_url, digest)
        
        # Save to database
        import json, uuid
        cursor.execute("""
            INSERT INTO digests (id, content, sent_to)
            VALUES (%s, %s, %s)
        """, (str(uuid.uuid4()), digest, "terminal" if not slack_url else "slack"))
        conn.commit()
        
        return {
            "status": "success",
            "message": "Digest sent successfully.",
            "clusters_included": len(clusters),
            "pending_proposals": pending_proposals
        }
    
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        cursor.close()
        conn.close()


def _format_digest(clusters, top_proposals, health) -> str:
    """Formats the digest as readable text."""
    
    date_str = datetime.now().strftime("%B %d, %Y")
    
    total, successes, failures, avg_latency, total_cost = health or (0, 0, 0, 0, 0)
    success_rate = round((successes / total * 100), 1) if total else 0
    
    lines = [
        f"📊 TraceFly Daily Digest — {date_str}",
        "",
        f"🏥 AGENT HEALTH (Last 24h)",
        f"   Total interactions: {total}",
        f"   Success rate: {success_rate}%",
        f"   Failures: {failures}",
        f"   Avg latency: {avg_latency}ms",
        f"   Total cost: ${total_cost}",
        "",
        "🔴 TOP FAILURE CLUSTERS",
    ]
    
    if not clusters:
        lines.append("   No clusters found yet. Need more traces.")
    else:
        for i, (desc, intent, error_mode, count, score, status) in enumerate(clusters):
            lines.append(f"   {i+1}. [{intent or 'unknown'}] {desc[:80]}...")
            lines.append(f"      Error: {error_mode} | {count} affected | Impact score: {score}")
    
    lines += ["", "💡 TOP PROPOSALS (ranked by confidence)"]
    
    if not top_proposals:
        lines.append("   No proposals yet. Run generate_suggestions() first.")
    else:
        for i, (hypothesis, score, explanation, risk, intent) in enumerate(top_proposals):
            # Confidence score visual bar: ████░░ style
            filled = int((score or 0) / 10 * 8)
            bar = "█" * filled + "░" * (8 - filled)
            
            lines.append(f"   {i+1}. [{intent}] {(hypothesis or '')[:75]}...")
            lines.append(f"      Confidence: {bar} {score}/10 | Risk: {risk}")
            if explanation:
                # Truncate explanation to one line for the digest
                short_exp = explanation[:100] + "..." if len(explanation) > 100 else explanation
                lines.append(f"      Why: {short_exp}")
    
    lines += [
        "",
        f"   {len(top_proposals)} proposal(s) pending review in the database.",
        "",
        "→ Query proposals table ordered by confidence_score to review."
    ]
    
    return "\n".join(lines)


def _send_to_slack(webhook_url: str, text: str) -> None:
    """Sends text to a Slack channel via webhook."""
    try:
        response = requests.post(
            webhook_url,
            json={"text": f"```{text}```"},
            timeout=10
        )
        if response.status_code != 200:
            print(f"[Digest] Slack returned {response.status_code}")
    except Exception as e:
        print(f"[Digest] Failed to send to Slack: {e}")
```

---

### Step 11.2 — Create the Main ADK Agent

This is where everything comes together. Create `tracefly_agent/__init__.py` (empty file).

Create `tracefly_agent/agent.py`:

```python
"""
TraceFly Analysis Agent

This is the main ADK agent. It orchestrates the four tools in sequence.

Run with:
    adk run tracefly_agent
    
Or the web UI:
    adk web .
"""
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

# Import our tools
from tracefly_agent.tools.enrich import enrich_traces
from tracefly_agent.tools.cluster import cluster_traces
from tracefly_agent.tools.score import score_clusters
from tracefly_agent.tools.suggest import generate_suggestions
from tracefly_agent.tools.digest import send_digest

# The agent uses Claude via LiteLLM
# LiteLLM is the bridge between ADK (which defaults to Gemini) and Claude
CLAUDE_MODEL = LiteLlm(model="anthropic/claude-sonnet-4-6")

root_agent = LlmAgent(
    name="tracefly_agent",
    model=CLAUDE_MODEL,
    
    description="TraceFly Analysis Agent — analyzes agent traces, finds failure patterns, and suggests improvements.",
    
    instruction="""You are the TraceFly Analysis Agent. Your job is to analyze AI agent traces and find patterns of failure.

When asked to run the analysis pipeline, follow these steps IN ORDER:

1. Call enrich_traces() to label all unenriched traces with intent, outcome, and error mode.
   - If it says "all caught up", proceed to step 2.
   - If it processes traces, proceed to step 2.

2. Call cluster_traces() to group similar failures together.
   - Use the default parameters (7 days, minimum 5 traces per cluster).
   - If no clusters are found, report this and stop.

3. Call score_clusters() to rank clusters by impact.
   - This tells us which problem to fix first.

4. Call generate_suggestions() to create prompt improvement proposals.
   - Generate suggestions for the top 3 clusters.

5. Call send_digest() to summarize the findings.
   - This prints the results and optionally sends to Slack.

After completing all steps, give a brief summary of:
- How many traces were processed
- How many clusters were found
- What the top problem is (highest impact cluster)
- How many proposals were generated

If any step fails, report the error clearly and continue with the remaining steps.
Do not skip any step unless it's impossible to proceed.""",
    
    tools=[
        enrich_traces,
        cluster_traces,
        score_clusters,
        generate_suggestions,
        send_digest,
    ]
)
```

---

## 12. Phase 7 — Demo Data Loader

**Goal:** One script that downloads a real public dataset and loads it into the database as realistic traces — no fake data, no API calls needed.  
**Time:** 1–2 days.

---

### Why the Bitext Dataset?

The **Bitext Customer Support dataset** on Hugging Face contains 26,872 real customer support instruction/response pairs across 27 intents — things like `track_order`, `cancel_order`, `get_refund`, `change_shipping_address`. It is:

- Free and public (CC BY 4.0 license)
- No account needed to download
- Already labelled with intent categories
- Realistic customer support language
- Downloaded with one line of Python via the `datasets` library

This means when a recruiter runs `make demo`, they see TraceFly analyzing **real customer support conversations** — not obviously fake generated text. That's far more impressive.

**What we do with it:**
1. Download it (one line)
2. Map its fields to TraceFly's trace schema
3. Synthetically add the missing operational fields (latency, cost, token count) with realistic random values
4. Inject a realistic failure pattern — returns and refund queries get a higher thumbs-down rate, simulating a known prompt weakness
5. Load it all into Postgres

---

### Step 12.1 — Create the Demo Loader

Create `demo/__init__.py` (empty file).

Create `demo/load_demo_data.py`:

```python
"""
TraceFly Demo Data Loader

Downloads the Bitext Customer Support dataset from Hugging Face
and loads it into the TraceFly database as realistic agent traces.

No API key needed. No account needed. Downloads ~5MB.

Usage:
    python demo/load_demo_data.py
    python demo/load_demo_data.py --limit 500   # load only 500 traces (faster)
    python demo/load_demo_data.py --reset        # clear existing data first
"""
import sys
import os
import uuid
import random
import argparse
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

# Add project root to path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import get_db_connection


# ── Realistic operational value ranges ───────────────────────────────────────
# These simulate what real agent telemetry looks like.
# Latency varies by query complexity; cost by token count.

LATENCY_BY_INTENT = {
    "track_order": (400, 900),
    "cancel_order": (600, 1400),
    "get_refund": (700, 1800),      # refunds are complex — higher latency
    "change_shipping_address": (500, 1100),
    "get_invoice": (300, 700),
    "contact_customer_service": (400, 900),
    "default": (400, 1200),
}

TOKEN_RANGE = (180, 520)            # typical support response token range
COST_PER_TOKEN = 0.000003           # approximate cost for Sonnet-class model

# ── Failure injection rules ───────────────────────────────────────────────────
# These simulate a realistic failure pattern: refund and return queries
# have a higher thumbs-down rate because the (imaginary) prompt is vague
# about policy. This is the core story TraceFly will tell.

FAILURE_RATES = {
    "get_refund": 0.45,             # 45% failure — the main cluster we want to find
    "cancel_order": 0.30,           # 30% failure — second cluster
    "get_invoice": 0.20,            # 20% failure
    "track_order": 0.08,            # 8% failure — mostly working fine
    "default": 0.10,
}

ESCALATION_RATES = {
    "get_refund": 0.20,
    "cancel_order": 0.12,
    "default": 0.03,
}

# ── Intent mapping ─────────────────────────────────────────────────────────────
# Bitext uses snake_case intent labels. We keep them as-is — they map
# cleanly to TraceFly's intent field.

BITEXT_TO_TRACEFLY_INTENT = {
    "track_order": "order_tracking",
    "cancel_order": "cancel_order",
    "change_order": "modify_order",
    "get_refund": "refund_request",
    "get_invoice": "billing_inquiry",
    "check_refund_policy": "refund_policy",
    "contact_customer_service": "general_inquiry",
    "check_cancellation_fee": "cancel_order",
    "track_refund": "refund_request",
    "change_shipping_address": "modify_order",
}


def load_demo_data(limit: int = 1000, reset: bool = False) -> None:
    """
    Main function. Downloads dataset and loads traces into Postgres.
    
    Args:
        limit: Maximum number of traces to load (default 1000, full dataset ~26K)
        reset: If True, clears all existing traces, clusters, and proposals first
    """
    
    print("📦 TraceFly Demo Data Loader")
    print("=" * 50)
    
    # Step 1: Download the dataset
    print("\n[1/4] Downloading Bitext Customer Support dataset from Hugging Face...")
    print("      (First run: ~5MB download. Cached after that.)")
    
    try:
        from datasets import load_dataset
        dataset = load_dataset(
            "bitext/Bitext-customer-support-llm-chatbot-training-dataset",
            split="train"
        )
        print(f"      ✅ Downloaded {len(dataset)} records")
    except Exception as e:
        print(f"      ❌ Download failed: {e}")
        print("      Make sure you ran: uv pip install -r requirements.txt")
        sys.exit(1)
    
    # Step 2: Connect to database
    print("\n[2/4] Connecting to database...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        print("      ✅ Connected")
    except Exception as e:
        print(f"      ❌ Database connection failed: {e}")
        print("      Make sure Docker is running: docker-compose up -d")
        sys.exit(1)
    
    # Step 3: Optionally reset existing data
    if reset:
        print("\n[3/4] Resetting existing data...")
        cursor.execute("DELETE FROM proposals")
        cursor.execute("DELETE FROM clusters")
        cursor.execute("DELETE FROM traces")
        conn.commit()
        print("      ✅ Cleared existing traces, clusters, and proposals")
    else:
        print("\n[3/4] Keeping existing data (use --reset to clear)")
    
    # Step 4: Transform and load
    print(f"\n[4/4] Loading up to {limit} traces into database...")
    
    # Shuffle so we get a mix of intents, not all the same type
    import random
    indices = list(range(len(dataset)))
    random.shuffle(indices)
    indices = indices[:limit]
    
    # Spread traces across the last 7 days so clustering has a time window
    now = datetime.now(timezone.utc)
    
    loaded = 0
    skipped = 0
    
    for i, idx in enumerate(indices):
        record = dataset[idx]
        
        instruction = record.get("instruction", "").strip()
        response = record.get("response", "").strip()
        raw_intent = record.get("intent", "general_inquiry").strip()
        
        # Skip empty records
        if not instruction or not response:
            skipped += 1
            continue
        
        # Map intent to TraceFly's labels
        intent = BITEXT_TO_TRACEFLY_INTENT.get(raw_intent, "general_inquiry")
        
        # Determine realistic failure pattern for this intent
        failure_rate = FAILURE_RATES.get(raw_intent, FAILURE_RATES["default"])
        escalation_rate = ESCALATION_RATES.get(raw_intent, ESCALATION_RATES["default"])
        
        # Simulate user feedback
        roll = random.random()
        if roll < failure_rate:
            user_feedback = "thumbs_down"
            escalation_flag = random.random() < escalation_rate
        elif roll < failure_rate + 0.35:
            user_feedback = "thumbs_up"
            escalation_flag = False
        else:
            user_feedback = None     # Most interactions have no explicit feedback
            escalation_flag = False
        
        # Simulate operational telemetry
        latency_range = LATENCY_BY_INTENT.get(raw_intent, LATENCY_BY_INTENT["default"])
        latency_ms = random.randint(*latency_range)
        
        token_count = random.randint(*TOKEN_RANGE)
        cost_usd = round(token_count * COST_PER_TOKEN, 6)
        
        # Spread created_at across last 7 days
        hours_back = random.uniform(0, 7 * 24)
        created_at = now - timedelta(hours=hours_back)
        
        # Insert into database
        try:
            cursor.execute("""
                INSERT INTO traces (
                    trace_id, session_id, user_input, final_output,
                    agent_steps, prompt_version_id, model_name,
                    token_count, cost_usd, latency_ms,
                    user_feedback, escalation_flag, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (trace_id) DO NOTHING
            """, (
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                instruction,
                response,
                "[]",                        # no tool calls in this dataset
                "v1.0",                      # prompt version — the thing TraceFly will suggest improving
                "claude-haiku-4-5-20251001", # model name
                token_count,
                cost_usd,
                latency_ms,
                user_feedback,
                escalation_flag,
                created_at
            ))
            loaded += 1
            
            # Commit every 100 rows and show progress
            if loaded % 100 == 0:
                conn.commit()
                print(f"      Loaded {loaded}/{len(indices)} traces...", end="\r")
        
        except Exception as e:
            skipped += 1
            if skipped < 5:   # Only print first few errors to avoid spam
                print(f"\n      Warning: Skipped record — {e}")
    
    conn.commit()
    
    # Summary
    print(f"\n\n✅ Done!")
    print(f"   Loaded:  {loaded} traces")
    print(f"   Skipped: {skipped} records (empty or duplicate)")
    
    # Show breakdown of what was loaded
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE user_feedback = 'thumbs_down') as failures,
            COUNT(*) FILTER (WHERE user_feedback = 'thumbs_up') as successes,
            COUNT(*) FILTER (WHERE escalation_flag = true) as escalations
        FROM traces
    """)
    stats = cursor.fetchone()
    print(f"\n   Database now contains:")
    print(f"   Total traces:    {stats[0]}")
    print(f"   Thumbs down:     {stats[1]} ({round(stats[1]/stats[0]*100, 1)}%)")
    print(f"   Thumbs up:       {stats[2]} ({round(stats[2]/stats[0]*100, 1)}%)")
    print(f"   Escalations:     {stats[3]}")
    print(f"\n   👉 Now run: make run")
    print(f"   👉 Then type: Run the full analysis pipeline")
    
    cursor.close()
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load demo data into TraceFly")
    parser.add_argument("--limit", type=int, default=1000,
                        help="Number of traces to load (default: 1000)")
    parser.add_argument("--reset", action="store_true",
                        help="Clear existing data before loading")
    args = parser.parse_args()
    
    load_demo_data(limit=args.limit, reset=args.reset)
```

Run it to verify:
```bash
python demo/load_demo_data.py --limit 200
```

You should see the download progress, then a summary showing traces loaded with a realistic failure rate. `get_refund` intent should show ~45% thumbs-down, which is the cluster TraceFly will discover.

---

## 13. Phase 8 — Makefile + One-Command Demo

**Goal:** A `Makefile` that wraps every command into simple shortcuts so any developer (or recruiter) can run the whole thing with three commands.  
**Time:** Half a day.

---

### What is a Makefile?

A Makefile is a list of shortcuts. Instead of remembering long commands, you type `make setup` and it runs everything for you. It's standard in open-source projects.

---

### Step 13.1 — Create the Makefile

Create `Makefile` in your `tracefly/` folder:

```makefile
# TraceFly MVP — Makefile
# Usage: make <target>
# Run 'make help' to see all commands

.PHONY: help setup db-start db-stop db-reset demo run clean

# ── Help ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  TraceFly MVP"
	@echo "  ─────────────────────────────────────────────"
	@echo "  First time setup:"
	@echo "    make setup       Install dependencies + start DB + load schema"
	@echo ""
	@echo "  Demo (for recruiters / quick showcase):"
	@echo "    make demo        Load real Bitext dataset + run full pipeline"
	@echo ""
	@echo "  Daily use:"
	@echo "    make run         Start the TraceFly agent (web UI)"
	@echo "    make db-start    Start the database (Docker)"
	@echo "    make db-stop     Stop the database"
	@echo "    make db-reset    Clear all data and reload demo dataset"
	@echo "  ─────────────────────────────────────────────"
	@echo ""

# ── First-time setup ──────────────────────────────────────────────────────────
setup:
	@echo "🔧 Setting up TraceFly..."
	@echo ""
	@echo "[1/4] Checking .env file..."
	@test -f .env || (cp .env.example .env && echo "      Created .env from .env.example — please add your ANTHROPIC_API_KEY")
	@echo "[2/4] Starting database..."
	docker-compose up -d
	@echo "      Waiting for Postgres to be ready..."
	@sleep 5
	@echo "[3/4] Running database schema..."
	docker exec -i tracefly_db psql -U tracefly -d tracefly < database/schema.sql
	@echo "[4/4] Installing Python dependencies..."
	uv pip install -r requirements.txt
	@echo ""
	@echo "✅ Setup complete!"
	@echo ""
	@echo "   Next steps:"
	@echo "   1. Add your ANTHROPIC_API_KEY to .env"
	@echo "   2. Run: make demo"
	@echo ""

# ── Database controls ─────────────────────────────────────────────────────────
db-start:
	@echo "🐘 Starting database..."
	docker-compose up -d
	@echo "✅ Database running at localhost:5432"

db-stop:
	@echo "🛑 Stopping database..."
	docker-compose down
	@echo "✅ Database stopped (data is saved)"

db-reset:
	@echo "🔄 Resetting database and reloading demo data..."
	python demo/load_demo_data.py --reset --limit 1000
	@echo "✅ Database reset with fresh demo data"

# ── Demo ──────────────────────────────────────────────────────────────────────
demo:
	@echo ""
	@echo "🎬 TraceFly Demo"
	@echo "════════════════════════════════════════════"
	@echo ""
	@echo "Step 1: Loading real customer support data from Hugging Face..."
	python demo/load_demo_data.py --limit 1000
	@echo ""
	@echo "Step 2: Starting TraceFly agent..."
	@echo ""
	@echo "════════════════════════════════════════════"
	@echo "  In the chat that opens, type:"
	@echo "  → 'Run the full analysis pipeline'"
	@echo "════════════════════════════════════════════"
	@echo ""
	adk web .

# ── Run ───────────────────────────────────────────────────────────────────────
run:
	@echo "🚀 Starting TraceFly agent (web UI)..."
	@echo "   Open: http://localhost:8000"
	@echo "   Type: 'Run the full analysis pipeline'"
	@echo ""
	adk web .

run-cli:
	@echo "🚀 Starting TraceFly agent (CLI mode)..."
	adk run tracefly_agent

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean:
	@echo "🧹 Cleaning up..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Cleaned"
```

---

### Step 13.2 — Create the README

This is what a recruiter or developer sees first when they visit your GitHub repo. It must get them running in under 5 minutes.

Create `README.md`:

```markdown
# TraceFly — AI Agent Improvement Copilot

> Automatically finds failure patterns in your LLM agent traces and suggests prompt fixes.

Built with **Google ADK** · **Claude (Anthropic)** · **Postgres + pgvector**

---

## What it does

TraceFly wraps your LLM agent, collects every interaction as a trace, then:
1. **Observes** — captures inputs, outputs, tool calls, latency, feedback
2. **Analyzes** — clusters failure traces into named patterns with impact scores
3. **Suggests** — generates concrete prompt change proposals with before/after diffs

---

## Try it in 3 commands

**Prerequisites:** Python 3.11+, Docker Desktop, an Anthropic API key

```bash
git clone https://github.com/yourname/tracefly
cd tracefly
cp .env.example .env          # then add your ANTHROPIC_API_KEY to .env
make setup                    # installs deps, starts DB, runs schema
make demo                     # loads real data + opens the agent
```

In the chat that opens at http://localhost:8000, type:
```
Run the full analysis pipeline
```

You'll see TraceFly analyze 1,000 real customer support conversations,
find failure clusters, score them by impact, and propose prompt fixes.

---

## Demo dataset

Uses the [Bitext Customer Support dataset](https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset)
from Hugging Face — 26,872 real customer support conversations, free and public.
Downloaded automatically on first run. No account needed.

---

## Add to your own agent

```python
from sdk.capture import capture_trace

# After your agent runs, add this:
capture_trace(
    user_input=user_message,
    final_output=agent_response,
    model_name="claude-sonnet-4-6",
    prompt_version_id="v1.0"
)
```

---

## Commands

| Command | What it does |
|---|---|
| `make setup` | First-time setup |
| `make demo` | Load demo data + start agent |
| `make run` | Start agent (assumes data already loaded) |
| `make db-start` | Start database |
| `make db-stop` | Stop database |
| `make db-reset` | Clear data and reload demo dataset |
```

---

### Step 13.3 — Create the .env.example

Already covered in Phase 0 Step 5.5. Make sure this file exists and is committed to GitHub. It's the only configuration file that goes in the repo.

---

### Step 13.4 — Test the Full Flow End-to-End

This is your final verification before calling the MVP done.

```bash
# Start fresh
make db-stop
make db-start

# Run schema
docker exec -i tracefly_db psql -U tracefly -d tracefly < database/schema.sql

# Load demo data
python demo/load_demo_data.py --limit 500

# Start the agent
make run
```

In the web UI at http://localhost:8000:
1. Select `tracefly_agent` from the top-left dropdown
2. Type: `Run the full analysis pipeline`
3. Watch it call each tool in sequence
4. Read the digest at the end

**What you should see at the end:**
- 2–4 clusters found, with `get_refund` and `cancel_order` as the top two (highest failure rate)
- Impact scores showing refund cluster as the priority
- 4–6 proposals with concrete prompt diffs
- A digest summarising everything

If you see this, the MVP is working. Record a Loom here.

---

## 14. How to Run and Demo the System

---

### For Yourself (Daily Development)

```bash
# Start the database (if not already running)
make db-start

# Start the agent with web UI
make run

# Open http://localhost:8000 in your browser
# Type: "Run the full analysis pipeline"
```

---

### For a Recruiter or Anyone Cloning the Repo

They do exactly this:

```bash
git clone https://github.com/yourname/tracefly
cd tracefly
cp .env.example .env
# Edit .env and add ANTHROPIC_API_KEY
make setup
make demo
```

`make demo` loads 1,000 real customer support traces from Hugging Face and opens the ADK web UI. They type one sentence and see the full pipeline run.

---

### What the Demo Output Looks Like

After typing `Run the full analysis pipeline`, the agent calls tools one by one and you see something like:

```
[TraceFly] enrich_traces() → Enriched 1000 traces. 0 errors.
[TraceFly] cluster_traces() → Found 4 clusters from 847 failure/near-miss traces.
[TraceFly] score_clusters() → Scored 4 clusters. Top cluster score: 435.
[TraceFly] generate_suggestions() → Generated 8 proposals for 4 clusters.
                                     Confidence scores range from 5.5 to 8.5.
[TraceFly] send_digest() → Digest sent.

📊 TraceFly Daily Digest — June 27, 2026

🏥 AGENT HEALTH (Last 7 days)
   Total interactions: 1000
   Success rate: 57%
   Failures: 387
   Avg latency: 834ms
   Total cost: $1.4820

🔴 TOP FAILURE CLUSTERS
   1. [refund_request] Agent provides vague refund timelines without
      referencing specific policy, causing re-escalation...
      Error: ux_confusion | 153 affected | Impact score: 612

   2. [cancel_order] Agent acknowledges cancellation but does not
      confirm success or provide a reference number...
      Error: hallucination | 89 affected | Impact score: 356

   3. [billing_inquiry] Agent confuses invoice and order confirmation
      documents, sending users to the wrong portal section...
      Error: retrieval_miss | 61 affected | Impact score: 305

💡 TOP PROPOSALS (ranked by confidence)

   1. [refund_request] Add explicit refund timeline instruction referencing
      the 5-10 business day SLA stated in policy section 4.2...
      Confidence: ███████░ 8.5/10 | Risk: low
      Why: All 12 failure examples show agent omitting the timeline.
           Fix directly targets the missing instruction. Score not 10
           because retrieval of policy doc cannot be ruled out.

   2. [cancel_order] Require agent to confirm cancellation status and
      provide order reference number in every cancellation response...
      Confidence: ██████░░ 7.5/10 | Risk: low
      Why: Failure pattern is consistent — agent says "cancelled" without
           confirming. Success examples always include a reference number.

   3. [refund_request] Restructure response format to lead with timeline
      before explaining process steps...
      Confidence: █████░░░ 6.0/10 | Risk: medium
      Why: Format change may help but root cause is likely missing
           instruction not format. Moderate confidence only.

   8 proposal(s) pending review in the database.

→ Query proposals table ordered by confidence_score to review.
```

---

### Viewing the Raw Data

If you want to browse tables directly, connect any Postgres viewer to:
- Host: `localhost` / Port: `5432`
- Database: `tracefly` / User: `tracefly` / Password: `tracefly_local`

Free options: **TablePlus** (Mac/Windows/Linux), **DBeaver** (cross-platform), or the psql CLI:
```bash
docker exec -it tracefly_db psql -U tracefly -d tracefly
# Then: SELECT * FROM clusters ORDER BY impact_score DESC;
```

---

## 15. Troubleshooting Common Problems

---

**Problem: `ModuleNotFoundError: No module named 'google.adk'`**  
Fix: Your virtual environment is not activated. Run `source .venv/bin/activate` (Mac/Linux) or `.venv\Scripts\activate` (Windows) and try again.

---

**Problem: `connection refused` on database**  
Fix: Docker is not running the database. Run `make db-start` (or `docker-compose up -d`) and wait 5 seconds before trying again. Verify with `docker-compose ps` — you should see `tracefly_db` with status `Up`.

---

**Problem: `ANTHROPIC_API_KEY not found`**  
Fix: Make sure `.env` exists (not just `.env.example`) and contains your real key. Run `cat .env` to check. Make sure every Python file that needs it calls `load_dotenv()` at the top.

---

**Problem: Dataset download fails**  
Fix: Check your internet connection. The Bitext dataset downloads from Hugging Face (~5MB). If it keeps failing, try: `python -c "from datasets import load_dataset; load_dataset('bitext/Bitext-customer-support-llm-chatbot-training-dataset', split='train')"` to see the exact error.

---

**Problem: ADK agent doesn't call any tools**  
Fix: Every tool function must have a docstring. ADK reads the docstring to understand what the tool does — without it, Claude doesn't know the tool exists. Check that every function in `tools/` has a docstring starting with a description.

---

**Problem: Clustering finds 0 clusters**  
Fix: You need enough failure traces. Check with:
```bash
docker exec -it tracefly_db psql -U tracefly -d tracefly \
  -c "SELECT outcome, COUNT(*) FROM traces GROUP BY outcome;"
```
If failures < 10, run `make db-reset` to reload 1,000 traces. If still 0 clusters, lower `min_cluster_size` from 5 to 3 in `tools/cluster.py`.

---

**Problem: `make` command not found on Windows**  
Fix: Windows doesn't have `make` by default. Install it via: `winget install GnuWin32.Make` or just run the commands manually — look inside the `Makefile` to see what each target runs and paste those commands directly.

---

## 16. What Comes After MVP

Once the MVP is running and you trust the data:

**Week 7–8: Add a Simple UI**
- Build a Next.js app that displays clusters and proposals in a browser
- Connect it directly to Postgres (or Supabase if you've switched)
- This replaces reading the terminal output

**Week 9–10: Add Eval Suite Generation**
- Turn representative traces into structured eval cases
- Build a simple eval runner that tests prompt changes against historical traces

**Week 11–12: Add Scheduling**
- Use a cron job to run the TraceFly agent every morning automatically
- No more manually typing "run analysis pipeline"

**Quarter 2: A/B Testing**
- Add a routing layer that splits traffic between prompt versions
- Compare metrics across variants
- This is Phase 3 from the PRD

---

## Quick Reference Card

```
FIRST TIME:
git clone / cd tracefly / cp .env.example .env / add API key / make setup / make demo

DAILY WORKFLOW:
make db-start                         ← start database
make run                              ← open agent at http://localhost:8000
→ type: "Run the full analysis pipeline"
→ read digest, review proposals in DB
make db-stop                          ← stop database when done

DEMO FOR RECRUITERS:
make setup && make demo               ← full demo in 2 commands (after adding API key)

KEY FILES:
sdk/capture.py              ← add to YOUR agent (3 lines)
demo/load_demo_data.py      ← loads Bitext dataset for demos
tracefly_agent/agent.py     ← the ADK agent definition
tools/enrich.py             ← labels traces
tools/cluster.py            ← groups failures
tools/score.py              ← ranks by impact
tools/suggest.py            ← generates proposals
tools/digest.py             ← sends summary
Makefile                    ← all shortcuts
docker-compose.yml          ← starts Postgres

VIEW DATA DIRECTLY:
docker exec -it tracefly_db psql -U tracefly -d tracefly
→ SELECT * FROM clusters ORDER BY impact_score DESC;
→ SELECT hypothesis, confidence_score, confidence_explanation, risk_level
     FROM proposals WHERE review_status = 'pending'
     ORDER BY confidence_score DESC;
→ SELECT * FROM traces WHERE cluster_id = '<cluster-uuid>';  -- drill into any cluster
```

---

*TraceFly MVP Build Plan v1.2 — Built with Google ADK + Claude (Anthropic) + Docker Postgres + pgvector*  
*Demo data: Bitext Customer Support Dataset (Hugging Face, CC BY 4.0)*  
*v1.2 changes: Docker-first setup · Bitext demo dataset · full cluster trace references · proposal reasoning + confidence scoring*
