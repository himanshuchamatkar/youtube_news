-- ======================================================================
-- Indian Stock Shorts Factory - Supabase Cloud Database Schema
-- Run this in your Supabase Dashboard -> SQL Editor -> New Query -> Run
-- ======================================================================

-- 1. settings table
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    is_encrypted BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. news_articles table
CREATE TABLE IF NOT EXISTS news_articles (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    url TEXT UNIQUE NOT NULL,
    source TEXT,
    provider TEXT,
    published_at TEXT,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    company TEXT,
    sector TEXT,
    country TEXT,
    relevance_score INTEGER DEFAULT 0,
    status TEXT DEFAULT 'raw',
    duplicate_of TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. daily_selections table
CREATE TABLE IF NOT EXISTS daily_selections (
    id TEXT PRIMARY KEY,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    news_article_id TEXT NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
    score INTEGER NOT NULL,
    selection_reason TEXT,
    is_test BOOLEAN DEFAULT FALSE,
    selected_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. scripts table
CREATE TABLE IF NOT EXISTS scripts (
    id TEXT PRIMARY KEY,
    news_article_id TEXT NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
    script TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    hashtags JSONB,
    model TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. video_jobs table
CREATE TABLE IF NOT EXISTS video_jobs (
    id TEXT PRIMARY KEY,
    job_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'QUEUED',
    progress INTEGER DEFAULT 0,
    current_stage TEXT DEFAULT 'queued',
    is_test BOOLEAN DEFAULT FALSE,
    execution_type TEXT DEFAULT 'public',
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error_message TEXT
);

-- 6. videos table
CREATE TABLE IF NOT EXISTS videos (
    id TEXT PRIMARY KEY,
    job_id TEXT REFERENCES video_jobs(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT,
    youtube_video_id TEXT UNIQUE,
    youtube_url TEXT,
    published_at TIMESTAMPTZ DEFAULT NOW(),
    video_path TEXT,
    status TEXT DEFAULT 'uploaded',
    duration INTEGER,
    tags TEXT,
    source_urls JSONB,
    is_test BOOLEAN DEFAULT FALSE
);

-- 7. job_logs table
CREATE TABLE IF NOT EXISTS job_logs (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES video_jobs(id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    duration REAL DEFAULT 0.0,
    error TEXT
);

-- 8. channel_metrics table
CREATE TABLE IF NOT EXISTS channel_metrics (
    id TEXT PRIMARY KEY,
    subscriber_count INTEGER DEFAULT 0,
    total_views INTEGER DEFAULT 0,
    total_likes INTEGER DEFAULT 0,
    total_comments INTEGER DEFAULT 0,
    captured_at TIMESTAMPTZ DEFAULT NOW()
);
