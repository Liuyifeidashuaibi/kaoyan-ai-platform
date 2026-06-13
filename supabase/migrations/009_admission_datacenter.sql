-- =============================================================================
-- 009_admission_datacenter.sql — 拟录取名单 / 专业统计 / 学校入口 / 爬虫任务
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. admission_records — 逐考生录取记录（Layer2 结构化层）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.admission_records (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  university_id    UUID NOT NULL REFERENCES public.universities (id) ON DELETE CASCADE,
  college_id       UUID REFERENCES public.colleges (id) ON DELETE SET NULL,
  major_id         UUID REFERENCES public.majors (id) ON DELETE SET NULL,
  year             INT  NOT NULL,
  candidate_no     TEXT,
  candidate_name   TEXT,
  initial_score    INT,
  retest_score     INT,
  final_score      INT,
  admission_status TEXT NOT NULL DEFAULT '拟录取',
  source_url       TEXT,
  source_title     TEXT,
  publish_date     DATE,
  raw_file_path    TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.admission_records IS '拟录取名单逐考生记录（真实上岸线数据源）';

CREATE INDEX IF NOT EXISTS idx_admission_records_uni_year
  ON public.admission_records (university_id, year);
CREATE INDEX IF NOT EXISTS idx_admission_records_major_year
  ON public.admission_records (major_id, year);

CREATE UNIQUE INDEX IF NOT EXISTS idx_admission_records_dedup
  ON public.admission_records (
    university_id,
    year,
    COALESCE(major_id, '00000000-0000-0000-0000-000000000000'::uuid),
    COALESCE(candidate_no, ''),
    COALESCE(initial_score, -1)
  );

-- ---------------------------------------------------------------------------
-- 2. major_statistics — 专业维度统计（Layer3 统计层）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.major_statistics (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  university_id   UUID NOT NULL REFERENCES public.universities (id) ON DELETE CASCADE,
  college_id      UUID REFERENCES public.colleges (id) ON DELETE SET NULL,
  major_id        UUID NOT NULL REFERENCES public.majors (id) ON DELETE CASCADE,
  year            INT  NOT NULL,
  min_score       INT,
  avg_score       NUMERIC(6, 2),
  max_score       INT,
  admitted_count  INT NOT NULL DEFAULT 0,
  retest_count    INT,
  admission_rate  NUMERIC(7, 4),
  retest_line     INT,
  quota           INT,
  exempt_count    INT,
  source_url      TEXT,
  source_title    TEXT,
  publish_date    DATE,
  raw_file_path   TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (major_id, year)
);

COMMENT ON TABLE public.major_statistics IS '专业年度录取统计（最低/平均/最高录取分）';

CREATE INDEX IF NOT EXISTS idx_major_statistics_uni_year
  ON public.major_statistics (university_id, year);

-- ---------------------------------------------------------------------------
-- 3. school_sources — 全国高校入口库
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.school_sources (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  university_id UUID REFERENCES public.universities (id) ON DELETE CASCADE,
  school_name   TEXT NOT NULL,
  graduate_url  TEXT,
  admission_url TEXT,
  notice_url    TEXT,
  college_urls  JSONB NOT NULL DEFAULT '[]'::jsonb,
  status        TEXT NOT NULL DEFAULT 'active',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (school_name)
);

COMMENT ON TABLE public.school_sources IS '院校研究生院/学院入口 URL 注册表';

CREATE INDEX IF NOT EXISTS idx_school_sources_university_id
  ON public.school_sources (university_id);

-- ---------------------------------------------------------------------------
-- 4. crawl_tasks — 爬虫任务队列（DB 持久化）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.crawl_tasks (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  university_id  UUID REFERENCES public.universities (id) ON DELETE SET NULL,
  school_name    TEXT,
  task_type      TEXT NOT NULL,
  target_url     TEXT,
  status         TEXT NOT NULL DEFAULT 'pending',
  priority       INT  NOT NULL DEFAULT 0,
  error_message  TEXT,
  payload        JSONB NOT NULL DEFAULT '{}'::jsonb,
  scheduled_at   TIMESTAMPTZ,
  started_at     TIMESTAMPTZ,
  finished_at    TIMESTAMPTZ,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.crawl_tasks IS '爬虫任务队列（discover/fetch/parse/extract）';

CREATE INDEX IF NOT EXISTS idx_crawl_tasks_status
  ON public.crawl_tasks (status, priority DESC, created_at);

-- ---------------------------------------------------------------------------
-- 5. updated_at 触发器
-- ---------------------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_admission_records_updated_at') THEN
    CREATE TRIGGER set_admission_records_updated_at
      BEFORE UPDATE ON public.admission_records
      FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_major_statistics_updated_at') THEN
    CREATE TRIGGER set_major_statistics_updated_at
      BEFORE UPDATE ON public.major_statistics
      FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_school_sources_updated_at') THEN
    CREATE TRIGGER set_school_sources_updated_at
      BEFORE UPDATE ON public.school_sources
      FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_crawl_tasks_updated_at') THEN
    CREATE TRIGGER set_crawl_tasks_updated_at
      BEFORE UPDATE ON public.crawl_tasks
      FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
  END IF;
END;
$$;

-- ---------------------------------------------------------------------------
-- 6. RLS — 公开只读
-- ---------------------------------------------------------------------------
ALTER TABLE public.admission_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.major_statistics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.school_sources     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crawl_tasks        ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='admission_records' AND policyname='admission_records are viewable by everyone') THEN
    CREATE POLICY "admission_records are viewable by everyone"
      ON public.admission_records FOR SELECT USING (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='major_statistics' AND policyname='major_statistics are viewable by everyone') THEN
    CREATE POLICY "major_statistics are viewable by everyone"
      ON public.major_statistics FOR SELECT USING (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='school_sources' AND policyname='school_sources are viewable by everyone') THEN
    CREATE POLICY "school_sources are viewable by everyone"
      ON public.school_sources FOR SELECT USING (true);
  END IF;
END;
$$;

-- ---------------------------------------------------------------------------
-- 7. 从 universities 初始化 school_sources
-- ---------------------------------------------------------------------------
INSERT INTO public.school_sources (university_id, school_name, graduate_url, status)
SELECT u.id, u.name, u.graduate_url, 'active'
FROM public.universities u
ON CONFLICT (school_name) DO UPDATE SET
  university_id = EXCLUDED.university_id,
  graduate_url  = COALESCE(EXCLUDED.graduate_url, public.school_sources.graduate_url),
  updated_at    = now();
