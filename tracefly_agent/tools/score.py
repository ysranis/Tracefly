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
                "scored": 0,
                "next_step": "Call generate_suggestions(top_n=3)"
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
            "message": (
                f"Scored {scored} clusters. Top cluster has impact score "
                f"{top_clusters[0]['impact_score'] if top_clusters else 0}."
            ),
            "next_step": "Call generate_suggestions(top_n=3)"
        }

    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        cursor.close()
        conn.close()
