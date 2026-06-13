-- =============================================================================
-- 007_choose_school_datacenter.sql — 择校数据中心扩展
-- 在现有 universities / majors / scores 上扩展，新增 colleges / source_pages
-- 并提供 schools / score_lines 兼容视图（对接 CTO 规范 API）
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. colleges 学院表（规范化，majors.college 文本可逐步迁移）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.colleges (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  university_id UUID NOT NULL REFERENCES public.universities (id) ON DELETE CASCADE,
  name          TEXT NOT NULL,
  official_site TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (university_id, name)
);

COMMENT ON TABLE public.colleges IS '院校下属学院（择校数据中心）';

CREATE INDEX IF NOT EXISTS idx_colleges_university_id ON public.colleges (university_id);

-- ---------------------------------------------------------------------------
-- 2. source_pages 来源页面注册表（Hash 增量检测）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.source_pages (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  university_id   UUID NOT NULL REFERENCES public.universities (id) ON DELETE CASCADE,
  url             TEXT NOT NULL,
  title           TEXT,
  page_type       TEXT,   -- 招生简章/复试线/专业目录/学院公告
  content_hash    TEXT,
  publish_date    DATE,
  last_fetch_time TIMESTAMPTZ,
  status          TEXT NOT NULL DEFAULT 'pending',  -- pending/ok/failed/skipped
  raw_file_path   TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (university_id, url)
);

COMMENT ON TABLE public.source_pages IS '爬虫来源页面注册与 Hash 追踪';

CREATE INDEX IF NOT EXISTS idx_source_pages_university_id ON public.source_pages (university_id);
CREATE INDEX IF NOT EXISTS idx_source_pages_hash ON public.source_pages (content_hash);

-- ---------------------------------------------------------------------------
-- 3. 扩展 majors / scores 字段（来源、置信度、学院 FK）
-- ---------------------------------------------------------------------------
ALTER TABLE public.majors
  ADD COLUMN IF NOT EXISTS college_id UUID REFERENCES public.colleges (id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS source_url TEXT;

ALTER TABLE public.majors
  ADD COLUMN IF NOT EXISTS status TEXT;

UPDATE public.majors SET status = 'active' WHERE status IS NULL;

ALTER TABLE public.majors
  ALTER COLUMN status SET DEFAULT 'active';

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'majors' AND column_name = 'status'
      AND is_nullable = 'YES'
  ) THEN
    ALTER TABLE public.majors ALTER COLUMN status SET NOT NULL;
  END IF;
END $$;

ALTER TABLE public.scores
  ADD COLUMN IF NOT EXISTS college_id UUID REFERENCES public.colleges (id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS score_type TEXT,
  ADD COLUMN IF NOT EXISTS remarks TEXT,
  ADD COLUMN IF NOT EXISTS source_url TEXT,
  ADD COLUMN IF NOT EXISTS publish_date DATE,
  ADD COLUMN IF NOT EXISTS confidence REAL,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

UPDATE public.scores SET score_type = '复试线' WHERE score_type IS NULL;
UPDATE public.scores SET updated_at = now() WHERE updated_at IS NULL;

ALTER TABLE public.scores
  ALTER COLUMN score_type SET DEFAULT '复试线',
  ALTER COLUMN updated_at SET DEFAULT now();

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'scores' AND column_name = 'score_type'
      AND is_nullable = 'YES'
  ) THEN
    ALTER TABLE public.scores ALTER COLUMN score_type SET NOT NULL;
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'scores' AND column_name = 'updated_at'
      AND is_nullable = 'YES'
  ) THEN
    ALTER TABLE public.scores ALTER COLUMN updated_at SET NOT NULL;
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 4. 兼容视图 — schools / score_lines（API 层可直接查询）
-- 注：001 迁移已存在 legacy 表 public.schools，需先重命名再建视图
-- ---------------------------------------------------------------------------
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relname = 'schools'
      AND c.relkind = 'r'  -- ordinary table
  ) THEN
    ALTER TABLE public.schools RENAME TO legacy_schools;
    COMMENT ON TABLE public.legacy_schools IS '001 遗留院校表（users.target_school_id 仍引用此表）';
  END IF;
END $$;

CREATE OR REPLACE VIEW public.schools AS
SELECT
  u.id,
  u.name,
  u.level_985       AS is_985,
  u.level_211       AS is_211,
  (u.double_first_class IS NOT NULL AND u.double_first_class <> '') AS is_double_first_class,
  u.website         AS official_site,
  u.graduate_url    AS graduate_site,
  u.province,
  u.city,
  u.school_type,
  u.intro,
  u.created_at,
  u.updated_at
FROM public.universities u;

CREATE OR REPLACE VIEW public.score_lines AS
SELECT
  s.id,
  s.university_id   AS school_id,
  s.college_id,
  s.major_id,
  s.year,
  s.score_type,
  s.total_score,
  s.politics_score,
  s.english_score,
  s.professional1_score AS major_one_score,
  s.professional2_score AS major_two_score,
  s.remarks,
  s.source_url,
  s.publish_date,
  s.confidence,
  s.created_at,
  s.updated_at
FROM public.scores s;

-- ---------------------------------------------------------------------------
-- 5. updated_at 触发器
-- ---------------------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_colleges_updated_at') THEN
    CREATE TRIGGER set_colleges_updated_at
      BEFORE UPDATE ON public.colleges
      FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_source_pages_updated_at') THEN
    CREATE TRIGGER set_source_pages_updated_at
      BEFORE UPDATE ON public.source_pages
      FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'set_scores_updated_at') THEN
    CREATE TRIGGER set_scores_updated_at
      BEFORE UPDATE ON public.scores
      FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
  END IF;
END;
$$;

-- ---------------------------------------------------------------------------
-- 6. RLS — 公开只读
-- ---------------------------------------------------------------------------
ALTER TABLE public.colleges     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.source_pages ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='colleges' AND policyname='colleges are viewable by everyone') THEN
    CREATE POLICY "colleges are viewable by everyone"
      ON public.colleges FOR SELECT USING (true);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='source_pages' AND policyname='source_pages are viewable by everyone') THEN
    CREATE POLICY "source_pages are viewable by everyone"
      ON public.source_pages FOR SELECT USING (true);
  END IF;
END;
$$;
