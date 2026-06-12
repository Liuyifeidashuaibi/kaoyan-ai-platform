-- =============================================================================
-- 005_crawler_fields.sql — AI 爬虫字段扩展
-- 为 universities 添加 school_code / graduate_url
-- 为动态表（announcements / recommendations / adjustments）添加
--   content_hash(TEXT)、last_updated(TIMESTAMPTZ)、content(TEXT)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. universities 扩展字段
-- ---------------------------------------------------------------------------
ALTER TABLE public.universities
  ADD COLUMN IF NOT EXISTS school_code  TEXT,          -- 教育部院校代码（5位，如"10001"）
  ADD COLUMN IF NOT EXISTS graduate_url TEXT;           -- 研究生院/研招网官网 URL

CREATE INDEX IF NOT EXISTS idx_universities_school_code
  ON public.universities (school_code);

-- ---------------------------------------------------------------------------
-- 2. announcements 扩展字段
-- ---------------------------------------------------------------------------
ALTER TABLE public.announcements
  ADD COLUMN IF NOT EXISTS content      TEXT,           -- AI 提取的内容摘要（100-200字）
  ADD COLUMN IF NOT EXISTS content_hash TEXT,           -- MD5(页面内容)，用于增量去重
  ADD COLUMN IF NOT EXISTS last_updated TIMESTAMPTZ DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_ann_content_hash  ON public.announcements (content_hash);
CREATE INDEX IF NOT EXISTS idx_ann_last_updated  ON public.announcements (last_updated DESC);

-- ---------------------------------------------------------------------------
-- 3. recommendations 扩展字段
-- ---------------------------------------------------------------------------
ALTER TABLE public.recommendations
  ADD COLUMN IF NOT EXISTS content      TEXT,
  ADD COLUMN IF NOT EXISTS content_hash TEXT,
  ADD COLUMN IF NOT EXISTS last_updated TIMESTAMPTZ DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_rec_content_hash  ON public.recommendations (content_hash);
CREATE INDEX IF NOT EXISTS idx_rec_last_updated  ON public.recommendations (last_updated DESC);

-- ---------------------------------------------------------------------------
-- 4. adjustments 扩展字段
-- ---------------------------------------------------------------------------
ALTER TABLE public.adjustments
  ADD COLUMN IF NOT EXISTS content_hash TEXT,
  ADD COLUMN IF NOT EXISTS last_updated TIMESTAMPTZ DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_adj_content_hash  ON public.adjustments (content_hash);
CREATE INDEX IF NOT EXISTS idx_adj_last_updated  ON public.adjustments (last_updated DESC);
