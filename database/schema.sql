-- Enable the vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- TABLE 1: traces
-- Stores every agent interaction
-- ============================================================
CREATE TABLE IF NOT EXISTS traces (
    -- Identity
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id              TEXT UNIQUE NOT NULL,   -- your agent's run ID
    session_id            TEXT,                   -- groups multi-turn conversations
    created_at            TIMESTAMPTZ DEFAULT NOW(),

    -- What happened
    user_input            TEXT,                   -- what the user said/sent
    final_output          TEXT,                   -- what the agent replied
    agent_steps           JSONB,                  -- tool calls, intermediate steps
    prompt_version_id     TEXT,                   -- which prompt was used

    -- Technical details
    model_name            TEXT,                   -- e.g. "claude-sonnet-4-6"
    token_count           INTEGER,
    cost_usd              NUMERIC(10, 6),
    latency_ms            INTEGER,

    -- Outcome signals
    user_feedback         TEXT,                   -- "thumbs_up", "thumbs_down", null
    escalation_flag       BOOLEAN DEFAULT FALSE,  -- was this handed off to a human?

    -- Enrichment (filled in by the Enrichment Agent later)
    intent                TEXT,                   -- e.g. "returns_policy"
    outcome               TEXT,                   -- "success", "failure", "near_miss"
    error_mode            TEXT,                   -- "hallucination", "tool_misuse", etc.
    enriched_at           TIMESTAMPTZ,            -- when enrichment ran

    -- Clustering (filled in by Clustering Agent)
    cluster_id            UUID,                   -- which cluster this trace belongs to
    embedding             vector(384)             -- the semantic vector (384 dims for MiniLM)
);

-- Index for fast lookups by time and outcome
CREATE INDEX IF NOT EXISTS idx_traces_created ON traces(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_traces_outcome ON traces(outcome);
CREATE INDEX IF NOT EXISTS idx_traces_cluster ON traces(cluster_id);
CREATE INDEX IF NOT EXISTS idx_traces_enriched ON traces(enriched_at)
    WHERE enriched_at IS NULL;  -- fast query for "unenriched traces"

-- Vector similarity index (HNSW is faster for search, IVFFlat for large scale)
CREATE INDEX IF NOT EXISTS idx_traces_embedding ON traces
    USING hnsw (embedding vector_cosine_ops);


-- ============================================================
-- TABLE 2: clusters
-- Groups of similar traces
-- ============================================================
CREATE TABLE IF NOT EXISTS clusters (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    updated_at            TIMESTAMPTZ DEFAULT NOW(),

    -- What the cluster is
    description           TEXT,           -- LLM-generated human-readable summary
    dominant_intent       TEXT,           -- most common intent in cluster
    dominant_error_mode   TEXT,           -- most common error type

    -- Size and impact
    trace_count           INTEGER DEFAULT 0,
    affected_user_count   INTEGER DEFAULT 0,
    impact_score          NUMERIC(6, 2),  -- calculated score for prioritization
    severity_weight       NUMERIC(4, 2),  -- based on error mode type

    -- Status tracking
    status                TEXT DEFAULT 'open',  -- "open", "in_progress", "resolved"

    -- Trace references — full traceability back to source data
    representative_trace_ids   JSONB,      -- top 5 example trace IDs (for display)
    all_trace_ids              JSONB,      -- ALL trace IDs in this cluster (for full drill-down)

    -- Time window this cluster covers
    window_start          TIMESTAMPTZ,
    window_end            TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_clusters_impact ON clusters(impact_score DESC);
CREATE INDEX IF NOT EXISTS idx_clusters_status ON clusters(status);


-- ============================================================
-- TABLE 3: proposals
-- Prompt change suggestions generated for each cluster
-- ============================================================
CREATE TABLE IF NOT EXISTS proposals (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id            UUID REFERENCES clusters(id),
    created_at            TIMESTAMPTZ DEFAULT NOW(),

    -- The suggestion
    hypothesis            TEXT,           -- "This change will reduce X because Y"
    reasoning             TEXT,           -- WHY this specific change — root cause analysis
    change_type           TEXT,           -- "instruction_addition", "constraint", etc.
    prompt_before         TEXT,           -- the current prompt section
    prompt_after          TEXT,           -- the proposed new version
    target_metric         TEXT,           -- what metric this aims to improve
    risk_level            TEXT,           -- "low", "medium", "high"

    -- Confidence scoring (Claude self-assesses how certain it is)
    confidence_score      NUMERIC(3, 1),  -- 0.0 to 10.0
    confidence_explanation TEXT,          -- plain-English explanation of the score

    ranking_score         NUMERIC(4, 2),

    -- Review
    review_status         TEXT DEFAULT 'pending',  -- "pending", "accepted", "rejected"
    review_notes          TEXT,           -- why rejected, or implementation notes
    reviewed_at           TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_proposals_cluster ON proposals(cluster_id);
CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(review_status);
CREATE INDEX IF NOT EXISTS idx_proposals_confidence ON proposals(confidence_score DESC);


-- ============================================================
-- TABLE 4: digests
-- History of summaries sent
-- ============================================================
CREATE TABLE IF NOT EXISTS digests (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    content               TEXT,           -- the full digest text
    clusters_included     JSONB,          -- which cluster IDs were in this digest
    sent_to               TEXT            -- "slack", "terminal", "email"
);
