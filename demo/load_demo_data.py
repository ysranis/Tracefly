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

    print("TraceFly Demo Data Loader")
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
        print(f"      Loaded {len(dataset)} records")
    except Exception as e:
        print(f"      Download failed: {e}")
        print("      Make sure you ran: uv pip install -r requirements.txt")
        sys.exit(1)

    # Step 2: Connect to database
    print("\n[2/4] Connecting to database...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        print("      Connected")
    except Exception as e:
        print(f"      Database connection failed: {e}")
        print("      Make sure Docker is running: docker-compose up -d")
        sys.exit(1)

    # Step 3: Optionally reset existing data
    if reset:
        print("\n[3/4] Resetting existing data...")
        cursor.execute("DELETE FROM proposals")
        cursor.execute("DELETE FROM clusters")
        cursor.execute("DELETE FROM traces")
        conn.commit()
        print("      Cleared existing traces, clusters, and proposals")
    else:
        print("\n[3/4] Keeping existing data (use --reset to clear)")

    # Step 4: Transform and load
    print(f"\n[4/4] Loading up to {limit} traces into database...")

    # Shuffle so we get a mix of intents, not all the same type
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
                "v1.0",                      # prompt version TraceFly will suggest improving
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
    print(f"\n\nDone!")
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
    print(f"\n   Next: make run")
    print(f"   Then type: Run the full analysis pipeline")

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
