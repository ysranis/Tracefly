"""
Tool 2: cluster_traces

Groups enriched failure traces into meaningful clusters using:
1. Embeddings (already computed during enrichment)
2. HDBSCAN clustering algorithm
3. Claude for generating human-readable cluster summaries
"""
import json
import uuid
import numpy as np
from datetime import datetime, timezone, timedelta
import hdbscan
import anthropic
import os
from database.db import get_db_connection


def cluster_traces(days_back: int = 7, min_cluster_size: int = 3) -> dict:
    """
    Clusters failure and near-miss traces from the past N days.

    Args:
        days_back: How many days of traces to cluster (default 7)
        min_cluster_size: Minimum traces to form a cluster (default 5)

    Returns:
        dict with status and list of clusters found
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Step 1: Get enriched failure/near-miss traces with embeddings
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

        cursor.execute("""
            SELECT id, trace_id, user_input, final_output,
                   intent, error_mode, outcome,
                   embedding::text
            FROM traces
            WHERE enriched_at IS NOT NULL
              AND outcome IN ('failure', 'near_miss')
              AND embedding IS NOT NULL
              AND created_at >= %s
            ORDER BY created_at DESC
        """, (cutoff,))

        rows = cursor.fetchall()

        if len(rows) < min_cluster_size:
            return {
                "status": "success",
                "message": f"Only {len(rows)} traces found. Need at least {min_cluster_size} to cluster.",
                "clusters_found": 0,
                "next_step": "Call score_clusters()"
            }

        print(f"[Cluster] Clustering {len(rows)} traces...")

        # Step 2: Extract embeddings into a numpy array
        trace_ids = []
        trace_data = []
        embeddings = []

        for row in rows:
            db_id, trace_id, user_input, final_output, \
                intent, error_mode, outcome, embedding_str = row

            # Parse the embedding string back into a list of floats
            embedding = json.loads(embedding_str)

            trace_ids.append(db_id)
            trace_data.append({
                "trace_id": trace_id,
                "user_input": user_input,
                "final_output": final_output,
                "intent": intent,
                "error_mode": error_mode,
                "outcome": outcome
            })
            embeddings.append(embedding)

        embedding_matrix = np.array(embeddings)

        # Step 3: Run HDBSCAN clustering
        # min_cluster_size: minimum number of traces to form a cluster
        # metric: cosine distance works well for text embeddings
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            metric='euclidean',  # We use euclidean on normalized vectors
            cluster_selection_method='eom'
        )

        # Normalize embeddings before clustering (improves cosine-like behavior)
        norms = np.linalg.norm(embedding_matrix, axis=1, keepdims=True)
        normalized = embedding_matrix / (norms + 1e-10)

        cluster_labels = clusterer.fit_predict(normalized)

        # cluster_labels is an array like: [0, 0, 1, -1, 0, 2, 1, ...]
        # -1 means "noise" (doesn't belong to any cluster) — we skip those
        unique_clusters = set(cluster_labels) - {-1}

        if not unique_clusters:
            return {
                "status": "success",
                "message": "No clusters found. Traces may be too diverse or too few.",
                "clusters_found": 0,
                "next_step": "Call score_clusters()"
            }

        print(f"[Cluster] Found {len(unique_clusters)} clusters")

        # Step 4: For each cluster, get representative traces and generate a summary
        claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

        clusters_created = []

        for cluster_label in unique_clusters:
            # Get indices of traces in this cluster
            cluster_indices = [i for i, label in enumerate(cluster_labels)
                               if label == cluster_label]

            cluster_traces_data = [trace_data[i] for i in cluster_indices]
            cluster_db_ids = [trace_ids[i] for i in cluster_indices]

            # Pick up to 5 representative traces (first 5 for MVP)
            representative_ids = cluster_db_ids[:5]

            # Determine dominant intent and error mode
            intents = [t["intent"] for t in cluster_traces_data if t["intent"]]
            error_modes = [t["error_mode"] for t in cluster_traces_data if t["error_mode"]]

            dominant_intent = _most_common(intents) or "unknown"
            dominant_error_mode = _most_common(error_modes) or "unknown"

            # Generate human-readable description using Claude
            description = _generate_cluster_description(
                claude, cluster_traces_data, dominant_intent, dominant_error_mode
            )

            # Save the cluster to the database
            # representative_trace_ids = top 5 shown in UI and used for suggestions
            # all_trace_ids = every trace in this cluster for full drill-down
            cluster_uuid = _save_cluster(
                cursor, conn,
                description=description,
                dominant_intent=dominant_intent,
                dominant_error_mode=dominant_error_mode,
                trace_count=len(cluster_indices),
                representative_trace_ids=representative_ids,
                all_trace_ids=cluster_db_ids,
                window_start=cutoff,
                window_end=datetime.now(timezone.utc)
            )

            # Update the cluster_id on all traces in this cluster
            cursor.execute("""
                UPDATE traces SET cluster_id = %s
                WHERE id = ANY(%s::uuid[])
            """, (cluster_uuid, cluster_db_ids))

            conn.commit()

            clusters_created.append({
                "cluster_id": str(cluster_uuid),
                "description": description[:100] + "...",
                "trace_count": len(cluster_indices),
                "dominant_intent": dominant_intent,
                "dominant_error_mode": dominant_error_mode
            })

        return {
            "status": "success",
            "clusters_found": len(clusters_created),
            "clusters": clusters_created,
            "message": f"Created {len(clusters_created)} clusters from {len(rows)} traces.",
            "next_step": "Call score_clusters()"
        }

    except Exception as e:
        conn.rollback()
        return {
            "status": "error",
            "message": f"Clustering failed: {str(e)}"
        }
    finally:
        cursor.close()
        conn.close()


def _most_common(lst: list):
    """Returns the most common element in a list."""
    if not lst:
        return None
    return max(set(lst), key=lst.count)


def _generate_cluster_description(claude, traces: list, intent: str, error_mode: str) -> str:
    """Asks Claude to write a human-readable cluster summary."""

    # Build examples from the first 3 traces
    examples = ""
    for i, t in enumerate(traces[:3]):
        examples += f"\nExample {i+1}:\n"
        examples += f"  User: {t['user_input'][:200]}\n"
        examples += f"  Agent: {t['final_output'][:200]}\n"

    response = claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": f"""You are analyzing a cluster of AI agent failures.

Dominant intent: {intent}
Dominant error type: {error_mode}
Number of affected interactions: {len(traces)}

Example failures:
{examples}

Write a 2-3 sentence description of what goes wrong in this cluster.
Be specific about WHAT the agent gets wrong and WHY it matters.
Do not use jargon. Write as if explaining to a product manager.
Do not include any preamble, just the description."""
        }]
    )

    return response.content[0].text.strip()


def _save_cluster(cursor, conn, **kwargs) -> str:
    """Saves a cluster to the database and returns its UUID.

    Stores both representative_trace_ids (top 5 for display) and
    all_trace_ids (every trace in the cluster for full traceability).
    This means you can always drill from a cluster back to every
    individual source trace that contributed to it.
    """

    cluster_uuid = str(uuid.uuid4())

    cursor.execute("""
        INSERT INTO clusters (
            id, description, dominant_intent, dominant_error_mode,
            trace_count, representative_trace_ids, all_trace_ids,
            window_start, window_end
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        cluster_uuid,
        kwargs["description"],
        kwargs["dominant_intent"],
        kwargs["dominant_error_mode"],
        kwargs["trace_count"],
        json.dumps([str(i) for i in kwargs["representative_trace_ids"]]),
        json.dumps([str(i) for i in kwargs["all_trace_ids"]]),
        kwargs["window_start"],
        kwargs["window_end"]
    ))

    return cursor.fetchone()[0]
