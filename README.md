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
