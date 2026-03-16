-- MOI Agent — Supabase setup
-- Run this in your Supabase SQL Editor (https://supabase.com/dashboard/project/qnchustgklovrtxbbnvp/sql)

-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Memories table
CREATE TABLE IF NOT EXISTS agent_memories (
    id bigserial PRIMARY KEY,
    content text NOT NULL,
    metadata jsonb DEFAULT '{}',
    embedding vector(768),
    created_at timestamptz DEFAULT now()
);

-- Vector similarity search index
CREATE INDEX IF NOT EXISTS idx_agent_memories_embedding
    ON agent_memories USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Semantic search function
CREATE OR REPLACE FUNCTION match_memories(
    query_embedding vector(768),
    match_threshold float DEFAULT 0.7,
    match_count int DEFAULT 5
)
RETURNS TABLE (
    id bigint,
    content text,
    metadata jsonb,
    similarity float
)
LANGUAGE sql STABLE
AS $$
    SELECT
        id,
        content,
        metadata,
        1 - (embedding <=> query_embedding) AS similarity
    FROM agent_memories
    WHERE 1 - (embedding <=> query_embedding) > match_threshold
    ORDER BY embedding <=> query_embedding
    LIMIT match_count;
$$;

-- Task history table (for analytics / snowball tracking)
CREATE TABLE IF NOT EXISTS agent_task_history (
    id bigserial PRIMARY KEY,
    task_id text NOT NULL,
    instruction text NOT NULL,
    status text NOT NULL,
    result text DEFAULT '',
    source text DEFAULT 'dashboard',
    steps jsonb DEFAULT '[]',
    duration_ms int,
    model_used text,
    created_at timestamptz DEFAULT now()
);
