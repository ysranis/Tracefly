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
                "proposals_created": 0,
                "next_step": "Call send_digest()"
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
            ),
            "next_step": "Call send_digest()"
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
    if success_examples:
        successes_text = "\nEXAMPLES OF CORRECT RESPONSES (same intent, different outcome):\n"
        for i, ex in enumerate(success_examples):
            successes_text += f"\nSUCCESS {i+1}:\n"
            successes_text += f"  User asked: {ex['user_input'][:200]}\n"
            successes_text += f"  Agent replied (correctly): {ex['final_output'][:200]}\n"
    else:
        successes_text = "\n(No success examples available for this intent yet.)\n"

    response = claude.messages.create(
        model="claude-haiku-4-5-20251001",
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

\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
FAILURE CLUSTER SUMMARY
\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
Description: {description}
Intent category: {intent}
Dominant error type: {error_mode}
Number of affected interactions: {trace_count}
Impact score: {impact_score}

\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
FAILURE EXAMPLES (what the agent got wrong)
\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
{failures_text}

\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
SUCCESS EXAMPLES (what good looks like)
\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
{successes_text}

\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
INSTRUCTIONS
\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
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
    "confidence_explanation": "Plain-English explanation of this score. What makes you confident? What uncertainty remains?"
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
