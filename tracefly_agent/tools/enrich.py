"""
Tool 1: enrich_traces

Reads unenriched traces from the database and adds:
- intent: what the user was trying to do
- outcome: did the agent succeed?
- error_mode: what type of failure (if any)?
- embedding: a vector representation for clustering later

Speed optimisations (Issue #9):
- Batch LLM calls: 10 traces per API call — reduces ~200 calls to ~17 per 100-trace batch
- Up to 20 concurrent batch calls via ThreadPoolExecutor (was 5 per-trace workers)
- Failures and near_misses prioritised in the fetch query so clustering
  gets useful data sooner even when the queue is large
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

    Uses batched API calls (10 traces per call, up to 20 concurrent batches).
    Failures and near_misses are fetched before successes so the clustering
    pipeline gets actionable data sooner.
    Call repeatedly until 'remaining' == 0.

    Args:
        batch_size: How many traces to process in one call (default 100)
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Fetch unenriched traces — failures and near_misses first (#2: priority ordering)
        cursor.execute("""
            SELECT id, trace_id, user_input, final_output,
                   user_feedback, escalation_flag, agent_steps
            FROM traces
            WHERE enriched_at IS NULL
            ORDER BY
                CASE WHEN user_feedback = 'thumbs_up'
                          AND COALESCE(escalation_flag, false) = false
                     THEN 1 ELSE 0 END ASC,
                created_at ASC
            LIMIT %s
        """, (batch_size,))

        rows = cursor.fetchall()

        if not rows:
            return {
                "status": "success",
                "message": "No unenriched traces found. All caught up!",
                "processed": 0,
                "remaining": 0,
                "next_step": "Call cluster_traces(days_back=7, min_cluster_size=3)"
            }

        print(f"[Enrich] Processing {len(rows)} traces...")

        claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        embedding_model = _get_embedding_model()

        # Phase 1: Rules-based outcome for all traces (no LLM)
        outcomes = {row[0]: _classify_outcome(row[4], row[5]) for row in rows}

        # Phase 2: Batch classify intents — 10 traces per API call, up to 20 concurrent (#1 + #3)
        print(f"[Enrich] Batch classifying intents ({len(rows)} traces, 10 per call)...")
        intent_map = _classify_intents_batch(claude, rows)

        # Phase 3: Batch classify error modes for non-successes only (#2 + #3)
        non_success_rows = [r for r in rows if outcomes[r[0]] != "success"]
        print(f"[Enrich] Batch classifying error modes ({len(non_success_rows)} non-success traces)...")
        error_mode_map = _classify_error_modes_batch(claude, non_success_rows)

        # Phase 4: Batch encode all embeddings in one call
        texts_to_embed = [
            f"{intent_map.get(row[0], 'other')} {row[2][:200]} {outcomes.get(row[0], 'near_miss')}"
            for row in rows
        ]
        embeddings = embedding_model.encode(texts_to_embed).tolist()
        embedding_map = {row[0]: emb for row, emb in zip(rows, embeddings)}

        # Phase 5: Batch write results to DB
        processed = 0
        now = datetime.now(timezone.utc)

        for row in rows:
            db_id = row[0]
            embedding = embedding_map.get(db_id)
            cursor.execute("""
                UPDATE traces
                SET intent = %s, outcome = %s, error_mode = %s,
                    embedding = %s::vector, enriched_at = %s
                WHERE id = %s
            """, (
                intent_map.get(db_id, "other"),
                outcomes.get(db_id, "near_miss"),
                error_mode_map.get(db_id),
                str(embedding) if embedding else None,
                now,
                db_id
            ))
            processed += 1

        conn.commit()

        # Count remaining unenriched
        cursor.execute("SELECT COUNT(*) FROM traces WHERE enriched_at IS NULL")
        remaining = cursor.fetchone()[0]

        if remaining > 0:
            next_step = f"Call enrich_traces() again — {remaining} traces still need enriching."
        else:
            next_step = "All traces enriched. Call cluster_traces(days_back=7, min_cluster_size=3)."

        return {
            "status": "success",
            "processed": processed,
            "remaining": remaining,
            "message": f"Enriched {processed} traces. {remaining} remaining.",
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


def _classify_outcome(user_feedback: str, escalation_flag: bool) -> str:
    """Rules-based outcome classification. No LLM needed."""
    if user_feedback == "thumbs_down":
        return "failure"
    if escalation_flag:
        return "failure"
    if user_feedback == "thumbs_up":
        return "success"
    return "near_miss"


# ---------------------------------------------------------------------------
# Batch intent classification (#3)
# ---------------------------------------------------------------------------

def _intent_batch_call(claude, batch: list) -> dict:
    """One Claude call classifying intent for up to 10 traces. Returns {db_id: intent}."""
    numbered = "\n\n".join([
        f"[{j + 1}] User: {row[2][:300]}\nAgent: {row[3][:300]}"
        for j, row in enumerate(batch)
    ])

    response = claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        messages=[{"role": "user", "content": f"""Classify the intent of each interaction. Reply ONLY with a JSON array of exactly {len(batch)} labels.

{numbered}

Valid labels: returns_policy, product_question, payment_issue, account_management, complaint, general_inquiry, technical_support, other

Reply ONLY with a JSON array. Example: ["returns_policy", "complaint"]"""}]
    )

    valid_intents = {
        "returns_policy", "product_question", "payment_issue",
        "account_management", "complaint", "general_inquiry",
        "technical_support", "other"
    }

    try:
        text = response.content[0].text.strip()
        # Strip markdown code blocks if present
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:])
            text = text.rsplit("```", 1)[0].strip()
        intents = json.loads(text)
        if isinstance(intents, list) and len(intents) == len(batch):
            return {
                row[0]: (intent if intent in valid_intents else "other")
                for row, intent in zip(batch, intents)
            }
    except (json.JSONDecodeError, ValueError, IndexError):
        pass

    return {row[0]: "other" for row in batch}


def _classify_intents_batch(claude, rows: list) -> dict:
    """Batch classify intent for all rows — 10 traces per API call, up to 20 concurrent."""
    BATCH_SIZE = 10
    batches = [rows[i:i + BATCH_SIZE] for i in range(0, len(rows), BATCH_SIZE)]
    results = {}

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(_intent_batch_call, claude, batch): batch for batch in batches}
        for future in as_completed(futures):
            batch = futures[future]
            try:
                results.update(future.result())
            except Exception:
                for row in batch:
                    results[row[0]] = "other"

    return results


# ---------------------------------------------------------------------------
# Batch error mode classification (#3)
# ---------------------------------------------------------------------------

def _error_mode_batch_call(claude, batch: list) -> dict:
    """One Claude call classifying error mode for up to 10 non-success traces."""
    result = {}
    needs_llm = []

    # Loop detection is rule-based — no LLM needed
    for row in batch:
        db_id, _, user_input, final_output, _, _, agent_steps_json = row
        if agent_steps_json:
            steps = (json.loads(agent_steps_json)
                     if isinstance(agent_steps_json, str) else agent_steps_json)
            tool_names = [s.get("tool") for s in steps if s.get("tool")]
            if len(tool_names) > 3 and len(set(tool_names)) < len(tool_names) / 2:
                result[db_id] = "loop"
                continue
        needs_llm.append(row)

    if not needs_llm:
        return result

    numbered = "\n\n".join([
        f"[{j + 1}] User: {row[2][:300]}\nAgent: {row[3][:300]}"
        for j, row in enumerate(needs_llm)
    ])

    response = claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": f"""Classify the failure type for each AI agent interaction. Reply ONLY with a JSON array of exactly {len(needs_llm)} labels.

{numbered}

Valid labels: hallucination, retrieval_miss, tool_misuse, ux_confusion, safety_violation, other_failure

Reply ONLY with a JSON array. Example: ["hallucination", "ux_confusion"]"""}]
    )

    valid_modes = {
        "hallucination", "retrieval_miss", "tool_misuse",
        "ux_confusion", "safety_violation", "other_failure"
    }

    try:
        text = response.content[0].text.strip()
        # Strip markdown code blocks if present
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:])
            text = text.rsplit("```", 1)[0].strip()
        modes = json.loads(text)
        if isinstance(modes, list) and len(modes) == len(needs_llm):
            for row, mode in zip(needs_llm, modes):
                result[row[0]] = mode if mode in valid_modes else "other_failure"
            return result
    except (json.JSONDecodeError, ValueError, IndexError):
        pass

    for row in needs_llm:
        result[row[0]] = "other_failure"
    return result


def _classify_error_modes_batch(claude, rows: list) -> dict:
    """Batch classify error mode for non-success rows — 10 per call, up to 20 concurrent."""
    if not rows:
        return {}

    BATCH_SIZE = 10
    batches = [rows[i:i + BATCH_SIZE] for i in range(0, len(rows), BATCH_SIZE)]
    results = {}

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(_error_mode_batch_call, claude, batch): batch for batch in batches}
        for future in as_completed(futures):
            batch = futures[future]
            try:
                results.update(future.result())
            except Exception:
                for row in batch:
                    results[row[0]] = "other_failure"

    return results
