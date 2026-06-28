"""
Tool 1: enrich_traces

Reads unenriched traces from the database and adds:
- intent: what the user was trying to do
- outcome: did the agent succeed?
- error_mode: what type of failure (if any)?
- embedding: a vector representation for clustering later

Speed: API calls run concurrently (ThreadPoolExecutor), embeddings are batch-encoded.
"""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from sentence_transformers import SentenceTransformer
from database.db import get_db_connection
import anthropic
import os

_embedding_model = None


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        print("[Enrich] Loading embedding model...")
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


def enrich_traces(batch_size: int = 100) -> dict:
    """
    Enriches the next batch of unenriched traces.

    Uses concurrent API calls and batch embedding for speed.
    Call repeatedly until 'remaining' == 0.

    Args:
        batch_size: How many traces to process in one call (default 100)
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
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
            cursor.execute("SELECT COUNT(*) FROM traces WHERE enriched_at IS NULL")
            remaining = cursor.fetchone()[0]
            return {
                "status": "success",
                "message": "No unenriched traces found. All caught up!",
                "processed": 0,
                "remaining": 0,
                "next_step": "Call cluster_traces(days_back=7, min_cluster_size=3)"
            }

        print(f"[Enrich] Processing {len(rows)} traces concurrently...")

        claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        embedding_model = _get_embedding_model()

        # Phase 1: Classify all traces concurrently (IO-bound API calls)
        # 5 workers keeps us well within Anthropic rate limits
        classifications = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(_classify_trace, claude, row): row[0]
                for row in rows
            }
            for future in as_completed(futures):
                db_id = futures[future]
                try:
                    classifications[db_id] = future.result()
                except Exception as e:
                    classifications[db_id] = {"error": str(e)}

        # Phase 2: Batch encode embeddings — much faster than one-by-one
        texts_to_embed = []
        ordered_db_ids = []
        for row in rows:
            db_id = row[0]
            cls = classifications.get(db_id, {})
            if not cls.get("error"):
                intent = cls.get("intent", "other")
                outcome = cls.get("outcome", "near_miss")
                user_input = row[2]
                texts_to_embed.append(f"{intent} {user_input[:200]} {outcome}")
                ordered_db_ids.append(db_id)

        embeddings = embedding_model.encode(texts_to_embed).tolist() if texts_to_embed else []
        embedding_map = dict(zip(ordered_db_ids, embeddings))

        # Phase 3: Batch write results to DB
        processed = 0
        errors = 0
        now = datetime.now(timezone.utc)

        for row in rows:
            db_id = row[0]
            cls = classifications.get(db_id, {})

            if cls.get("error"):
                errors += 1
                cursor.execute(
                    "UPDATE traces SET enriched_at = %s WHERE id = %s",
                    (now, db_id)
                )
            else:
                embedding = embedding_map.get(db_id)
                cursor.execute("""
                    UPDATE traces
                    SET intent = %s, outcome = %s, error_mode = %s,
                        embedding = %s::vector, enriched_at = %s
                    WHERE id = %s
                """, (
                    cls["intent"],
                    cls["outcome"],
                    cls["error_mode"],
                    str(embedding) if embedding else None,
                    now,
                    db_id
                ))
                processed += 1

        conn.commit()

        # Count how many traces still need enriching
        cursor.execute("SELECT COUNT(*) FROM traces WHERE enriched_at IS NULL")
        remaining = cursor.fetchone()[0]

        if remaining > 0:
            next_step = f"Call enrich_traces() again — {remaining} traces still need enriching."
        else:
            next_step = "All traces enriched. Call cluster_traces(days_back=7, min_cluster_size=3)."

        return {
            "status": "success",
            "processed": processed,
            "errors": errors,
            "remaining": remaining,
            "message": f"Enriched {processed} traces. {errors} errors. {remaining} remaining.",
            "next_step": next_step
        }

    except Exception as e:
        conn.rollback()
        return {
            "status": "error",
            "message": f"Enrichment failed: {str(e)}",
            "next_step": "Retry enrich_traces() or check database connection."
        }
    finally:
        cursor.close()
        conn.close()


def _classify_trace(claude, row) -> dict:
    """Classify a single trace. Runs concurrently in a thread pool."""
    _, trace_id, user_input, final_output, user_feedback, escalation_flag, agent_steps_json = row

    intent = _classify_intent(claude, user_input, final_output)
    outcome = _classify_outcome(user_feedback, escalation_flag)
    error_mode = _classify_error_mode(claude, user_input, final_output, outcome, agent_steps_json)

    return {"intent": intent, "outcome": outcome, "error_mode": error_mode}


def _classify_intent(claude, user_input: str, final_output: str) -> str:
    """Uses Claude Haiku to classify what the user was trying to do."""

    response = claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=20,
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
    valid_intents = [
        "returns_policy", "product_question", "payment_issue",
        "account_management", "complaint", "general_inquiry",
        "technical_support", "other"
    ]
    return intent if intent in valid_intents else "other"


def _classify_outcome(user_feedback: str, escalation_flag: bool) -> str:
    """Rules-based outcome classification. No LLM needed."""
    if user_feedback == "thumbs_down":
        return "failure"
    if escalation_flag:
        return "failure"
    if user_feedback == "thumbs_up":
        return "success"
    return "near_miss"


def _classify_error_mode(claude, user_input: str, final_output: str,
                          outcome: str, agent_steps_json) -> str:
    """Classifies failure type. Returns None for successes."""

    if outcome == "success":
        return None

    # Check for loops first — no LLM needed
    if agent_steps_json:
        steps = json.loads(agent_steps_json) if isinstance(agent_steps_json, str) \
                else agent_steps_json
        tool_names = [s.get("tool") for s in steps if s.get("tool")]
        if len(tool_names) > 3 and len(set(tool_names)) < len(tool_names) / 2:
            return "loop"

    response = claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=20,
        messages=[{
            "role": "user",
            "content": f"""What type of AI agent failure is this?

User asked: {user_input[:300]}
Agent answered: {final_output[:300]}

Choose ONE:
- hallucination
- retrieval_miss
- tool_misuse
- ux_confusion
- safety_violation
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
