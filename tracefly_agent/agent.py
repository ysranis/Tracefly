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
CLAUDE_MODEL = LiteLlm(model="anthropic/claude-haiku-4-5-20251001")

root_agent = LlmAgent(
    name="tracefly_agent",
    model=CLAUDE_MODEL,

    description="TraceFly Analysis Agent — analyzes agent traces, finds failure patterns, and suggests improvements.",

    instruction="""You are the TraceFly Analysis Agent. You analyze AI agent traces to find failure patterns and suggest fixes.

CORE RULE: Every tool response contains a "next_step" field. After EVERY tool call, read that field and immediately execute the instruction in it — no pausing, no asking the user, no summarizing mid-pipeline. Keep going until send_digest() completes.

PIPELINE (always runs to completion in this order):
  enrich_traces() → [loop until remaining=0] → cluster_traces() → score_clusters() → generate_suggestions() → send_digest()

Step-by-step rules:
1. Call enrich_traces(). If the response has remaining > 0, call enrich_traces() again immediately. Repeat until remaining == 0. Then call cluster_traces(days_back=7, min_cluster_size=3).
2. After cluster_traces(), always call score_clusters() regardless of how many clusters were found.
3. After score_clusters(), always call generate_suggestions(top_n=3).
4. After generate_suggestions(), always call send_digest().
5. Only after send_digest() completes, give the user a final summary.

Never stop between steps. Never ask the user what to do next. The next_step field tells you exactly what to call.""",

    tools=[
        enrich_traces,
        cluster_traces,
        score_clusters,
        generate_suggestions,
        send_digest,
    ]
)
