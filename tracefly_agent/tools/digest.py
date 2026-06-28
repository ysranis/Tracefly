"""
Digest Tool: Generates a human-readable summary of TraceFly findings.
Prints to terminal in MVP. Can be extended to send to Slack.
"""
import os
import json
import uuid
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
        print("\n" + "=" * 60)
        print(digest)
        print("=" * 60 + "\n")

        # Send to Slack if configured
        slack_url = os.environ.get("SLACK_WEBHOOK_URL")
        if slack_url:
            _send_to_slack(slack_url, digest)

        # Save to database
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
        f"TraceFly Daily Digest — {date_str}",
        "",
        "AGENT HEALTH (Last 24h)",
        f"   Total interactions: {total}",
        f"   Success rate: {success_rate}%",
        f"   Failures: {failures}",
        f"   Avg latency: {avg_latency}ms",
        f"   Total cost: ${total_cost}",
        "",
        "TOP FAILURE CLUSTERS",
    ]

    if not clusters:
        lines.append("   No clusters found yet. Need more traces.")
    else:
        for i, (desc, intent, error_mode, count, score, status) in enumerate(clusters):
            lines.append(f"   {i+1}. [{intent or 'unknown'}] {desc[:80]}...")
            lines.append(f"      Error: {error_mode} | {count} affected | Impact score: {score}")

    lines += ["", "TOP PROPOSALS (ranked by confidence)"]

    if not top_proposals:
        lines.append("   No proposals yet. Run generate_suggestions() first.")
    else:
        for i, (hypothesis, score, explanation, risk, intent) in enumerate(top_proposals):
            # Confidence score visual bar: filled/empty blocks
            filled = int((score or 0) / 10 * 8)
            bar = "#" * filled + "-" * (8 - filled)

            lines.append(f"   {i+1}. [{intent}] {(hypothesis or '')[:75]}...")
            lines.append(f"      Confidence: [{bar}] {score}/10 | Risk: {risk}")
            if explanation:
                short_exp = explanation[:100] + "..." if len(explanation) > 100 else explanation
                lines.append(f"      Why: {short_exp}")

    lines += [
        "",
        f"   {len(top_proposals)} proposal(s) pending review in the database.",
        "",
        "-> Query proposals table ordered by confidence_score to review."
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
