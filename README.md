# TraceFly — Product Manager's Guide
### What it is, how it works, and how to try it yourself

---

## What is TraceFly?

TraceFly is an AI agent that watches your LLM-powered products in production, finds patterns in where they fail, and tells you exactly what to fix in your prompt — with a confidence score and a plain-English explanation of why.

If you run any AI agent — a customer support bot, a sales assistant, a coding copilot — TraceFly sits quietly alongside it, records every interaction, and periodically runs an analysis that surfaces:

- **Which failure patterns are most common** and how many users they affect
- **Why they are happening** — hallucination, confusion, missing information, tool errors
- **What to change in your prompt** to fix them, with a before/after diff and a reasoning explanation

The output is a ranked, prioritised shortlist of problems and fixes — not a wall of logs.

---

## The Problem It Solves

Running an LLM agent in production means dealing with failures that are **silent and probabilistic**. Unlike a software bug that throws an error, an LLM failure looks like a response — it just happens to be wrong, vague, confusing, or off-policy.

Today most teams handle this by:
- Manually scrolling through logs hoping to spot something
- Reacting to user complaints or support escalations after the damage is done
- Changing prompts based on intuition with no way to know if the change helped

TraceFly replaces that with a systematic loop:

```
Agent runs → TraceFly records it → Clusters failures → Ranks by impact → Suggests fixes
```

The shift is from **reactive and gut-driven** to **proactive and evidence-driven**.

---

## Who This Is For

TraceFly is useful if you are:

- A **product manager** who owns an AI agent and wants to understand what is going wrong without needing to read thousands of log lines
- An **AI engineer** who wants a structured way to prioritise prompt improvements
- A **technical founder** evaluating what observability for AI agents should look like in practice

You do not need to understand machine learning to use it. The outputs — cluster descriptions, proposals, confidence scores — are written in plain English for decision-makers.

---

## How to Clone It and Run It Yourself

You need three things installed on your computer:
- **Python 3.11+** — download from python.org
- **Docker Desktop** — download from docker.com (free)
- **An Anthropic API key** — from console.anthropic.com

Then run these commands in your terminal:

```bash
# Step 1: Get the code
git clone https://github.com/yourname/tracefly
cd tracefly

# Step 2: Add your API key
cp .env.example .env
# Open .env in any text editor and replace:
# ANTHROPIC_API_KEY=your-anthropic-key-here
# with your real key

# Step 3: Set everything up (one command)
make setup

# Step 4: Run the demo
make demo
```

`make demo` downloads 1,000 real customer support conversations from a public dataset on Hugging Face, loads them into the database, and opens the TraceFly agent in your browser at `http://localhost:8000`.

In the chat that opens, type:
```
Run the full analysis pipeline
```

Within about 60 seconds you will see TraceFly find failure clusters, rank them, and generate prompt fix proposals — complete with reasoning and confidence scores.

**To stop everything when you are done:**
```bash
make db-stop
```

---

## How to Connect It to Your Own Data

TraceFly ships with a demo dataset so you can try it immediately. When you are ready to point it at your own agent, you add three lines of Python to wherever your agent produces a response:

```python
from sdk.capture import capture_trace

# Add this after your agent generates a response
capture_trace(
    user_input=what_the_user_said,
    final_output=what_the_agent_replied,
    model_name="claude-sonnet-4-6",      # or whichever model you use
    prompt_version_id="v1.0"             # label your current prompt version
)
```

That is the entire integration. Your agent's behaviour is unchanged — TraceFly silently records what happened and stores it for analysis. The next time you run the analysis pipeline, it will be working from your real production data instead of the demo dataset.

**Optional — record user feedback:**
```python
from sdk.capture import update_feedback

# Call this if your user clicks thumbs up or thumbs down
update_feedback(trace_id=trace_id, feedback="thumbs_down")
```

Feedback signals significantly improve TraceFly's ability to identify real failures vs near-misses, so it is worth adding if your product has any rating mechanism.

---

## What TraceFly Does Under the Hood

This section explains the full process from a trace arriving in the database to a prompt proposal appearing in the output. Each step is a separate tool (Python function) that the Claude orchestrator calls in sequence.

---

### Step 1 — Trace Capture

**What happens:** Every time your agent runs, a lightweight function records the interaction to a Postgres database. No LLM is involved at this stage — it is just saving data.

**What gets saved:**
- The user's message and the agent's response
- Which prompt version was used
- Which model was called
- How long it took (latency)
- How many tokens were used and what it cost
- Any feedback the user gave (thumbs up/down, escalation)
- The full list of tool calls if the agent used any

**Why this matters:** Everything downstream depends on having complete, structured records of what actually happened. Without this, you are guessing.

**What is not stored:** PII is masked at capture time — email addresses, phone numbers, and credit card patterns are automatically replaced with `[EMAIL]`, `[PHONE]`, `[CARD]` before anything is written to the database.

---

### Step 2 — Enrichment

**What happens:** A batch process runs over all unprocessed traces and adds three labels to each one. This is where Claude is first used.

**Label 1 — Intent:** What was the user trying to do?

Claude reads the user message and the agent response and classifies it into one of your defined intent categories — for example `refund_request`, `order_tracking`, `billing_inquiry`. This is the primary grouping dimension for clustering later.

A cheaper, faster Claude model (Haiku) handles this since it runs on every single trace and the task is straightforward classification.

**Label 2 — Outcome:** Did the agent succeed?

This is determined by rules, not an LLM, because rules are faster and more consistent for this type of signal:
- Explicit thumbs-down from the user → `failure`
- Escalated to a human agent → `failure`
- Explicit thumbs-up → `success`
- No signal either way → `near_miss`

Near-misses are included in clustering because they often represent quiet failures — interactions where the user gave up rather than complaining.

**Label 3 — Error mode:** If it failed, how did it fail?

TraceFly classifies failures into six types:

| Error Mode | What it means |
|---|---|
| `hallucination` | The agent stated something factually wrong |
| `retrieval_miss` | The agent lacked the information it needed |
| `tool_misuse` | The agent called a tool with wrong or missing parameters |
| `ux_confusion` | The response was so unclear the user had to ask again |
| `safety_violation` | The agent crossed a policy or safety boundary |
| `loop` | The agent repeated the same actions without making progress |

Loops are detected by counting repeated tool calls — no LLM needed. The others use a lightweight Claude call.

**Why enrichment is a separate step from capture:** Enrichment involves LLM calls which cost money and take time. Keeping them async and batched means your agent's response time is never affected by TraceFly.

---

### Step 3 — Embedding

**What happens:** Each enriched trace is converted into a list of numbers — called an embedding — that represents its meaning mathematically.

The tool concatenates the intent, the user message (first 200 characters), and the outcome into one piece of text, then passes it through a small, free embedding model (`all-MiniLM-L6-v2`) that runs locally on your machine.

The result is a list of 384 numbers that captures the semantic meaning of that interaction. Traces about similar topics — even if worded differently — end up with similar numbers. This is what makes clustering possible.

**Analogy:** Think of it like plotting every trace on a map. Traces about return policy questions cluster on one part of the map. Traces about payment failures cluster on another. The embedding is each trace's coordinates on that map.

---

### Step 4 — Clustering

**What happens:** An algorithm called HDBSCAN looks at the coordinates of all failure and near-miss traces and finds natural groups — dense areas on the map where many traces sit close together.

Unlike simpler clustering algorithms, HDBSCAN does not require you to tell it how many groups to look for. It finds them itself, and it can handle situations where some traces don't belong to any group (they are labelled as noise and ignored for now).

The result is a set of clusters, each containing the IDs of every trace that belongs to it.

**Then Claude writes a description for each cluster.** It reads up to three representative failure traces from the cluster and writes a 2–3 sentence plain-English summary of what goes wrong:

> *"Agent provides vague refund timelines without referencing the specific 5–10 business day SLA. All examples in this cluster involve users who asked a follow-up question immediately after, suggesting the initial answer did not resolve their query."*

**Why this is valuable:** Instead of reading 153 individual failure traces, you read one paragraph. The paragraph tells you what all 153 traces have in common.

**Full traceability:** Every trace in a cluster has its `cluster_id` recorded, and every cluster stores the IDs of all its traces. You can always drill from a cluster description back to the individual conversations that made it up.

---

### Step 5 — Impact Scoring

**What happens:** Each cluster gets a numeric impact score that reflects how urgently it needs to be fixed.

The formula is:

```
impact_score = number_of_affected_traces × severity_weight
```

Severity weights by failure type:

| Failure type | Weight | Rationale |
|---|---|---|
| Safety violation | 10 | Regulatory and brand risk — zero tolerance |
| Hallucination | 8 | Directly damages user trust |
| Tool misuse | 7 | Can cause incorrect real-world actions |
| Retrieval miss | 5 | Reduces helpfulness but less immediately harmful |
| UX confusion | 4 | Drives abandonment and re-work |
| Loop | 4 | Wastes cost and user time |

A cluster with 50 hallucination traces scores `50 × 8 = 400`. A cluster with 100 UX confusion traces scores `100 × 4 = 400`. They tie — which is correct, because both represent meaningful problems of similar scale despite different failure types.

The output is a ranked list of clusters from highest to lowest impact score. This is your prioritised backlog of what to fix.

---

### Step 6 — Suggestion Generation

**What happens:** For the top 3 clusters by impact score, Claude generates two concrete prompt change proposals each.

This is where the most sophisticated reasoning in the system happens. Claude receives:
- The cluster description
- Up to 3 failure examples (what the agent got wrong)
- Up to 2 success examples from the same intent (what a good response looks like)
- The dominant error type and impact score

It uses the contrast between failures and successes to diagnose the root cause — not just what went wrong, but why — and proposes a specific change to the prompt that addresses that root cause.

**Each proposal contains:**

**Hypothesis** — one sentence stating what is being changed and what outcome is expected.
> *"Adding an explicit instruction to always cite the refund timeline from policy section 4.2 will reduce vague responses and cut escalation rate for refund queries."*

**Reasoning** — 2–4 sentences explaining the root cause and why this fix addresses it.
> *"The failure traces show a consistent pattern: the agent acknowledges the refund request but never states a timeframe. The success examples all include '5–10 business days' in the first sentence. The current prompt says 'be helpful about refunds' but does not instruct the agent to reference the specific SLA. Adding that explicit instruction directly addresses the gap."*

**Before/after diff** — literal prompt text the developer can copy and paste.
> Before: `"Answer refund questions helpfully and empathetically."`  
> After: `"When answering refund questions, always state the 5–10 business day processing timeline in your first sentence. Reference this as our standard policy. Be empathetic but specific."`

**Confidence score (0–10)** — how certain Claude is that this change will help.

**Confidence explanation** — why the score is what it is, including what uncertainty remains.
> *"8.5/10. High confidence because all 12 failure examples show the same missing step and the fix is targeted. Score is not 10 because we cannot rule out a retrieval issue also contributing — worth monitoring after implementation."*

**Why confidence scores matter:** A proposal with a 9.0 is one you implement immediately. A proposal with a 5.0 is one you investigate further before acting. The score saves you from blindly implementing suggestions that are educated guesses.

---

### Step 7 — Digest

**What happens:** A summary of the full analysis is formatted and printed to the terminal (and optionally sent to Slack).

It shows:
- Agent health over the last 24 hours (success rate, failures, latency, cost)
- Top failure clusters ranked by impact score
- Top proposals ranked by confidence score, with their reasoning
- A count of proposals pending review

This is the output a PM or team lead reads. It is designed to be actionable without requiring any database access.

---

## The Full Flow in One Picture

```
Your agent runs
      ↓
Trace saved to Postgres (instant, no LLM)
      ↓
Enrichment agent adds: intent + outcome + error mode (async, Claude Haiku)
      ↓
Embedding model converts each trace to a vector (local, free)
      ↓
HDBSCAN clustering finds natural failure groups
      ↓
Claude writes a plain-English description for each cluster
      ↓
Impact scoring ranks clusters by severity × scale
      ↓
Claude analyses top clusters and generates prompt proposals
  — with hypothesis, reasoning, diff, and confidence score
      ↓
Digest printed to terminal / sent to Slack
      ↓
You review proposals and implement the highest-confidence ones
```

---

## How to Review Proposals

Proposals are stored in the database and can be reviewed by running:

```bash
docker exec -it tracefly_db psql -U tracefly -d tracefly
```

Then:
```sql
SELECT hypothesis, confidence_score, risk_level, prompt_before, prompt_after
FROM proposals
WHERE review_status = 'pending'
ORDER BY confidence_score DESC;
```

Or if you prefer a visual tool, connect **TablePlus** (free, from tableplus.com) to `localhost:5432` with username and password both set to `tracefly`.

To mark a proposal as accepted:
```sql
UPDATE proposals SET review_status = 'accepted' WHERE id = '<proposal-id>';
```

To reject with a note:
```sql
UPDATE proposals 
SET review_status = 'rejected', review_notes = 'Root cause is retrieval not prompt'
WHERE id = '<proposal-id>';
```

Once you accept a proposal, implement the `prompt_after` text in your actual agent prompt. Then let TraceFly run again after a few days of traffic to see whether the failure cluster shrinks.

---

## Next Steps

**Immediate — connect your own agent**  
Add the three-line SDK integration to your agent (see "How to Connect It to Your Own Data" above). Let it run for a week with real traffic before triggering the analysis pipeline. The more traces, the better the clusters.

**Short term — add user feedback signals**  
If your product has any rating or escalation mechanism, wire it to `update_feedback()`. Even a simple thumbs up/down dramatically improves the quality of outcome classification, which improves cluster accuracy downstream.

**Medium term — build a simple UI**  
The terminal digest and SQL queries work for technical users. A lightweight Next.js dashboard that displays clusters, proposals, and their confidence scores in a browser makes TraceFly accessible to the whole product team without anyone needing to touch a database.

**Medium term — scheduling**  
Right now the analysis pipeline runs when you manually trigger it. Adding a cron job or scheduled task to run it every morning means your team gets a fresh digest without anyone having to remember to run a command.

**Longer term — offline eval and A/B testing**  
The next major capability after the current MVP is turning accepted proposals into structured test cases and running controlled experiments to validate that prompt changes actually improve metrics before rolling them out fully. This is Phase 2 and Phase 3 of the TraceFly roadmap — documented in the full PRD in the repository.

---

## Useful Commands

| Command | What it does |
|---|---|
| `make setup` | First-time setup — installs dependencies, starts database, runs schema |
| `make demo` | Loads demo dataset and opens the agent |
| `make run` | Opens the agent (assuming data is already loaded) |
| `make db-start` | Starts the database |
| `make db-stop` | Stops the database |
| `make db-reset` | Clears all data and reloads the demo dataset |

---

## Questions?

The full technical build plan, architecture decisions, and PRD are in the repository. If you want to understand a specific part of the system in more depth — the clustering algorithm, the confidence scoring logic, or the database schema — the build plan documents every decision and the reasoning behind it.

---

*TraceFly MVP — Built with Google ADK · Claude (Anthropic) · Postgres + pgvector*  
*Demo data: Bitext Customer Support Dataset (Hugging Face, CC BY 4.0)*
