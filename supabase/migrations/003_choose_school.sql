-- =============================================================================
-- 003_choose_school.sql — 985/211/双一流择校功能
-- 创建 universities / majors / scores / announcements / recommendations /
-- adjustments 六张新表，并与现有 schools 表保持独立
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. universities 院校主表
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.universities (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name                TEXT NOT NULL UNIQUE,
  logo_url            TEXT,
  province            TEXT NOT NULL,
  city                TEXT NOT NULL,
  level_985           BOOLEAN NOT NULL DEFAULT false,
  level_211           BOOLEAN NOT NULL DEFAULT false,
  double_first_class  TEXT,            -- 一流大学A/一流大学B/一流学科
  school_type         TEXT NOT NULL,   -- 综合/理工/师范/财经/政法/医药/农林/艺术
  intro               TEXT,
  address             TEXT,
  website             TEXT,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.universities IS '985/211/双一流院校信息（择校模块专用）';

CREATE INDEX IF NOT EXISTS idx_universities_level
  ON public.universities (level_985, level_211, double_first_class);
CREATE INDEX IF NOT EXISTS idx_universities_province
  ON public.universities (province);

-- ---------------------------------------------------------------------------
-- 2. majors 专业表（择校模块，字段比旧 majors 更丰富）
-- ---------------------------------------------------------------------------
-- 注：已存在旧 majors 表，此处使用 IF NOT EXISTS 避免冲突
-- 如需全量替换，请先 DROP TABLE public.majors CASCADE;
CREATE TABLE IF NOT EXISTS public.majors (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  university_id       UUID NOT NULL REFERENCES public.universities (id) ON DELETE CASCADE,
  college             TEXT NOT NULL,
  name                TEXT NOT NULL,
  code                TEXT NOT NULL,
  degree_type         TEXT NOT NULL,   -- 学硕/专硕
  study_mode          TEXT NOT NULL,   -- 全日制/非全日制
  exam_type           TEXT DEFAULT '统考',
  enrollment_count    INT,
  subject_category    TEXT,            -- 学科门类（哲学/经济学/…）
  first_discipline    TEXT,            -- 一级学科名称
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (university_id, code, degree_type, study_mode)
);

COMMENT ON TABLE public.majors IS '院校专业目录（择校模块）';

CREATE INDEX IF NOT EXISTS idx_majors_university_id ON public.majors (university_id);
CREATE INDEX IF NOT EXISTS idx_majors_code          ON public.majors (code);

-- ---------------------------------------------------------------------------
-- 3. scores 分数线表
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.scores (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  university_id       UUID NOT NULL REFERENCES public.universities (id) ON DELETE CASCADE,
  major_id            UUID NOT NULL REFERENCES public.majors (id) ON DELETE CASCADE,
  year                INT  NOT NULL,
  total_score         INT  NOT NULL,
  politics_score      INT  NOT NULL,
  english_score       INT  NOT NULL,
  professional1_score INT,
  professional2_score INT,
  line_diff           INT,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (major_id, year)
);

COMMENT ON TABLE public.scores IS '历年复试/录取分数线';

CREATE INDEX IF NOT EXISTS idx_scores_university_id ON public.scores (university_id);
CREATE INDEX IF NOT EXISTS idx_scores_major_id      ON public.scores (major_id);
CREATE INDEX IF NOT EXISTS idx_scores_year          ON public.scores (year DESC);

-- ---------------------------------------------------------------------------
-- 4. announcements 公告表
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.announcements (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  university_id  UUID NOT NULL REFERENCES public.universities (id) ON DELETE CASCADE,
  title          TEXT NOT NULL,
  publish_time   DATE NOT NULL,
  url            TEXT NOT NULL,
  type           TEXT NOT NULL,   -- 招生简章/招生公告/调剂公告/推免公告
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (university_id, url)
);

COMMENT ON TABLE public.announcements IS '院校招生相关公告';

CREATE INDEX IF NOT EXISTS idx_announcements_university_id ON public.announcements (university_id);
CREATE INDEX IF NOT EXISTS idx_announcements_type          ON public.announcements (type);

-- ---------------------------------------------------------------------------
-- 5. recommendations 推免信息表
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.recommendations (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  university_id  UUID NOT NULL REFERENCES public.universities (id) ON DELETE CASCADE,
  title          TEXT NOT NULL,
  type           TEXT NOT NULL,   -- 夏令营/预推免/正式推免
  status         TEXT NOT NULL,   -- 未开始/报名中/已结束
  start_time     DATE,
  end_time       DATE,
  url            TEXT NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (university_id, url)
);

COMMENT ON TABLE public.recommendations IS '推免/夏令营信息';

CREATE INDEX IF NOT EXISTS idx_recommendations_university_id ON public.recommendations (university_id);

-- ---------------------------------------------------------------------------
-- 6. adjustments 调剂信息表
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.adjustments (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  university_id  UUID NOT NULL REFERENCES public.universities (id) ON DELETE CASCADE,
  major_id       UUID REFERENCES public.majors (id) ON DELETE SET NULL,
  year           INT  NOT NULL,
  major_name     TEXT NOT NULL,
  quota          INT,
  requirements   TEXT,
  contact        TEXT,
  url            TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (university_id, major_name, year)
);

COMMENT ON TABLE public.adjustments IS '历年调剂信息';

CREATE INDEX IF NOT EXISTS idx_adjustments_university_id ON public.adjustments (university_id);
CREATE INDEX IF NOT EXISTS idx_adjustments_year          ON public.adjustments (year DESC);

-- ---------------------------------------------------------------------------
-- 7. updated_at 自动更新触发器
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'set_universities_updated_at'
  ) THEN
    CREATE TRIGGER set_universities_updated_at
      BEFORE UPDATE ON public.universities
      FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'set_majors_choose_updated_at'
  ) THEN
    CREATE TRIGGER set_majors_choose_updated_at
      BEFORE UPDATE ON public.majors
      FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
  END IF;
END;
$$;

-- ---------------------------------------------------------------------------
-- 8. Row Level Security — 全部公开只读（写入由爬虫 service_role key 完成）
-- ---------------------------------------------------------------------------
ALTER TABLE public.universities    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.majors          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scores          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.announcements   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.adjustments     ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  -- universities
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='universities' AND policyname='universities are viewable by everyone') THEN
    CREATE POLICY "universities are viewable by everyone"
      ON public.universities FOR SELECT USING (true);
  END IF;
  -- majors
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='majors' AND policyname='majors are viewable by everyone') THEN
    CREATE POLICY "majors are viewable by everyone"
      ON public.majors FOR SELECT USING (true);
  END IF;
  -- scores
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='scores' AND policyname='scores are viewable by everyone') THEN
    CREATE POLICY "scores are viewable by everyone"
      ON public.scores FOR SELECT USING (true);
  END IF;
  -- announcements
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='announcements' AND policyname='announcements are viewable by everyone') THEN
    CREATE POLICY "announcements are viewable by everyone"
      ON public.announcements FOR SELECT USING (true);
  END IF;
  -- recommendations
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='recommendations' AND policyname='recommendations are viewable by everyone') THEN
    CREATE POLICY "recommendations are viewable by everyone"
      ON public.recommendations FOR SELECT USING (true);
  END IF;
  -- adjustments
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='adjustments' AND policyname='adjustments are viewable by everyone') THEN
    CREATE POLICY "adjustments are viewable by everyone"
      ON public.adjustments FOR SELECT USING (true);
  END IF;
END;
$$;
