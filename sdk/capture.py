"""
TraceFly SDK — Trace Capture

This is the ONLY file you need to add to your existing agent.
Usage in your agent:
    from sdk.capture import capture_trace

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
import re
from contextlib import contextmanager
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
    # Email addresses
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                  '[EMAIL]', text)

    # Phone numbers (basic international format)
    text = re.sub(r'\b(\+?[\d\s\-\(\)]{7,15})\b', '[PHONE]', text)

    # Credit card patterns (16 digits)
    text = re.sub(r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b',
                  '[CARD]', text)

    return text


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
