-- Database Migration: Initialize Schema for Indian Stock Market News Shorts Factory

-- Drop tables if they exist (clean setup)
DROP TABLE IF EXISTS video_metrics CASCADE;
DROP TABLE IF EXISTS channel_metrics CASCADE;
DROP TABLE IF EXISTS videos CASCADE;
DROP TABLE IF EXISTS job_logs CASCADE;
DROP TABLE IF EXISTS video_jobs CASCADE;
DROP TABLE IF EXISTS scripts CASCADE;
DROP TABLE IF EXISTS daily_selections CASCADE;
DROP TABLE IF EXISTS news_articles CASCADE;
DROP TABLE IF EXISTS settings CASCADE;
DROP TABLE IF EXISTS system_events CASCADE;

-- 1. settings table: Key-value store for system configurations and keys
CREATE TABLE settings (
    key VARCHAR(255) PRIMARY KEY,
    value TEXT NOT NULL,
    is_encrypted BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. news_articles table: Raw and filtered articles
CREATE TABLE news_articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT,
    url TEXT UNIQUE NOT NULL,
    source TEXT,
    provider VARCHAR(50), -- newsapi, gnews, finnhub, rss
    published_at TIMESTAMP WITH TIME ZONE,
    fetched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    company VARCHAR(255),
    sector VARCHAR(255),
    country VARCHAR(100),
    relevance_score INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'raw', -- raw, qualified, rejected, selected
    duplicate_of UUID REFERENCES news_articles(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for URL lookups and status filtering
CREATE INDEX idx_news_articles_url ON news_articles(url);
CREATE INDEX idx_news_articles_status ON news_articles(status);
CREATE INDEX idx_news_articles_published_at ON news_articles(published_at);

-- 3. daily_selections table: Holds the single best article selected each day
CREATE TABLE daily_selections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    news_article_id UUID NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
    score INTEGER NOT NULL,
    selection_reason TEXT,
    is_test BOOLEAN DEFAULT FALSE,
    selected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enforce exactly one production selection per day
CREATE UNIQUE INDEX idx_daily_selections_prod_date ON daily_selections(date) WHERE (is_test = FALSE);

-- 4. scripts table: Generated script details for selected articles
CREATE TABLE scripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    news_article_id UUID NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
    script TEXT NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    hashtags TEXT[],
    model VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. video_jobs table: Job pipeline tracker
CREATE TABLE video_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_date DATE NOT NULL DEFAULT CURRENT_DATE,
    status VARCHAR(50) NOT NULL DEFAULT 'QUEUED', -- QUEUED, RUNNING, FETCHING_NEWS, FILTERING, ANALYZING, SCRIPT_GENERATING, VOICE_GENERATING, VISUAL_GENERATING, VIDEO_RENDERING, QUALITY_CHECK, UPLOADING, COMPLETED, FAILED, SKIPPED
    progress INTEGER DEFAULT 0,
    current_stage VARCHAR(100) DEFAULT 'queued',
    is_test BOOLEAN DEFAULT FALSE,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT
);

-- Enforce exactly one production job per day
CREATE UNIQUE INDEX idx_video_jobs_prod_date ON video_jobs(job_date) WHERE (is_test = FALSE);

-- Index for job date
CREATE INDEX idx_video_jobs_date ON video_jobs(job_date);

-- 6. videos table: Final published YouTube videos
CREATE TABLE videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES video_jobs(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    youtube_video_id VARCHAR(100) UNIQUE,
    youtube_url VARCHAR(255),
    published_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    duration INTEGER, -- duration in seconds
    source_urls TEXT[],
    status VARCHAR(50) DEFAULT 'draft' -- draft, uploaded, failed
);

-- 7. job_logs table: Verbose logs for tracing and debugging pipeline execution
CREATE TABLE job_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES video_jobs(id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    stage VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL, -- SUCCESS, FAILED, INFO, WARNING
    message TEXT,
    duration NUMERIC, -- stage duration in seconds
    error TEXT
);

CREATE INDEX idx_job_logs_job_id ON job_logs(job_id);

-- 8. channel_metrics table: Channel analytics caches
CREATE TABLE channel_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscriber_count INTEGER,
    total_views BIGINT,
    total_likes BIGINT,
    total_comments BIGINT,
    captured_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 9. video_metrics table: Individual video analytics histories
CREATE TABLE video_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    captured_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 10. system_events table: Generic platform alerts (e.g. key expired, restart)
CREATE TABLE system_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100),
    message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
