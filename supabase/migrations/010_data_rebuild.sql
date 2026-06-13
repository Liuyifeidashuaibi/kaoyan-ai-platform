-- =============================================================================
-- 010_data_rebuild.sql — 择校数据重建：新表 + 专业主数据字段
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Phase 5: majors 主数据字段补全
-- ---------------------------------------------------------------------------
ALTER TABLE public.majors
  ADD COLUMN IF NOT EXISTS master_type TEXT,
  ADD COLUMN IF NOT EXISTS last_verified_at TIMESTAMPTZ;

COMMENT ON COLUMN public.majors.master_type IS '学术型/专业型（由 degree_type 映射）';
COMMENT ON COLUMN public.majors.last_verified_at IS '最近一次官方来源校验时间';

UPDATE public.majors
SET master_type = CASE
  WHEN degree_type = '学硕' THEN '学术型'
  WHEN degree_type = '专硕' THEN '专业型'
  ELSE master_type
END
WHERE master_type IS NULL AND degree_type IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Phase 6: source_sites — 官方来源库
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.source_sites (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id       UUID REFERENCES public.universities (id) ON DELETE SET NULL,
  site_type       TEXT NOT NULL CHECK (
    site_type IN ('graduate_school', 'college_site', 'admission_site', 'notice_site')
  ),
  url             TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'active',
  last_check_time TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (school_id, site_type, url)
);

COMMENT ON TABLE public.source_sites IS '院校/学院官方来源 URL 注册表';

CREATE INDEX IF NOT EXISTS idx_source_sites_school_id ON public.source_sites (school_id);
CREATE INDEX IF NOT EXISTS idx_source_sites_status ON public.source_sites (status);

-- ---------------------------------------------------------------------------
-- Phase 7: admission_batches — 招生公告批次（监控发现的新公告）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.admission_batches (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id      UUID REFERENCES public.universities (id) ON DELETE SET NULL,
  college_id     UUID REFERENCES public.colleges (id) ON DELETE SET NULL,
  year           INT NOT NULL,
  batch_type     TEXT NOT NULL,
  title          TEXT NOT NULL,
  source_url     TEXT NOT NULL,
  publish_date   DATE,
  crawl_time     TIMESTAMPTZ NOT NULL DEFAULT now(),
  verify_status  TEXT NOT NULL DEFAULT 'pending'
    CHECK (verify_status IN ('official', 'pending', 'invalid')),
  content_hash   TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (school_id, source_url)
);

COMMENT ON TABLE public.admission_batches IS '官方招生公告批次（简章/目录/复试/拟录取/调剂）';

CREATE INDEX IF NOT EXISTS idx_admission_batches_school_year
  ON public.admission_batches (school_id, year DESC);

-- ---------------------------------------------------------------------------
-- Phase 8: raw_files — 原始文件永久保存
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.raw_files (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_id    UUID REFERENCES public.admission_batches (id) ON DELETE SET NULL,
  school_id   UUID REFERENCES public.universities (id) ON DELETE SET NULL,
  file_name   TEXT NOT NULL,
  file_type   TEXT NOT NULL,
  file_path   TEXT NOT NULL,
  file_hash   TEXT,
  file_size   BIGINT,
  source_url  TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.raw_files IS '原始公告文件归档（html/pdf/doc/xlsx 等），school 删除后仍可访问';

CREATE INDEX IF NOT EXISTS idx_raw_files_school_id ON public.raw_files (school_id);
CREATE INDEX IF NOT EXISTS idx_raw_files_batch_id ON public.raw_files (batch_id);
CREATE INDEX IF NOT EXISTS idx_raw_files_hash ON public.raw_files (file_hash);

-- ---------------------------------------------------------------------------
-- Phase 9: major_year_stats — 年度官方招生统计（仅 verify_status=official）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.major_year_stats (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  major_id           UUID NOT NULL REFERENCES public.majors (id) ON DELETE CASCADE,
  school_id          UUID NOT NULL REFERENCES public.universities (id) ON DELETE CASCADE,
  college_id         UUID REFERENCES public.colleges (id) ON DELETE SET NULL,
  year               INT NOT NULL,
  quota              INT,
  exempt_count       INT,
  retest_line        INT,
  retest_min_score   INT,
  admitted_min_score INT,
  admitted_avg_score NUMERIC(6, 2),
  source_url         TEXT,
  publish_date       DATE,
  crawl_time         TIMESTAMPTZ NOT NULL DEFAULT now(),
  verify_status      TEXT NOT NULL DEFAULT 'pending'
    CHECK (verify_status IN ('official', 'pending', 'invalid')),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (major_id, year)
);

COMMENT ON TABLE public.major_year_stats IS '专业年度官方统计（仅可追溯来源）';

CREATE INDEX IF NOT EXISTS idx_major_year_stats_school_year
  ON public.major_year_stats (school_id, year DESC);

-- ---------------------------------------------------------------------------
-- parse_jobs — 解析失败入队人工审核
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.parse_jobs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_id      UUID REFERENCES public.admission_batches (id) ON DELETE SET NULL,
  raw_file_id   UUID REFERENCES public.raw_files (id) ON DELETE SET NULL,
  job_type      TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'pending',
  error_message TEXT,
  result        JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.parse_jobs IS '解析任务队列（失败入队人工审核）';

CREATE INDEX IF NOT EXISTS idx_parse_jobs_status
  ON public.parse_jobs (status, created_at);

-- ---------------------------------------------------------------------------
-- updated_at 触发器
-- ---------------------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_source_sites_updated_at') THEN
    CREATE TRIGGER set_source_sites_updated_at
      BEFORE UPDATE ON public.source_sites
      FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_admission_batches_updated_at') THEN
    CREATE TRIGGER set_admission_batches_updated_at
      BEFORE UPDATE ON public.admission_batches
      FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_major_year_stats_updated_at') THEN
    CREATE TRIGGER set_major_year_stats_updated_at
      BEFORE UPDATE ON public.major_year_stats
      FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_parse_jobs_updated_at') THEN
    CREATE TRIGGER set_parse_jobs_updated_at
      BEFORE UPDATE ON public.parse_jobs
      FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
  END IF;
END;
$$;

-- ---------------------------------------------------------------------------
-- RLS — 公开只读
-- ---------------------------------------------------------------------------
ALTER TABLE public.source_sites       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.admission_batches  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.raw_files          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.major_year_stats   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.parse_jobs         ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='source_sites' AND policyname='source_sites are viewable by everyone') THEN
    CREATE POLICY "source_sites are viewable by everyone"
      ON public.source_sites FOR SELECT USING (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='admission_batches' AND policyname='admission_batches are viewable by everyone') THEN
    CREATE POLICY "admission_batches are viewable by everyone"
      ON public.admission_batches FOR SELECT USING (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='raw_files' AND policyname='raw_files are viewable by everyone') THEN
    CREATE POLICY "raw_files are viewable by everyone"
      ON public.raw_files FOR SELECT USING (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='major_year_stats' AND policyname='major_year_stats are viewable by everyone') THEN
    CREATE POLICY "major_year_stats are viewable by everyone"
      ON public.major_year_stats FOR SELECT USING (true);
  END IF;
END;
$$;
