-- =============================================================================
-- 004_schools_extensions.sql — 择校模块补充扩展
-- 在 003_choose_school.sql 基础上增加：
--   - majors 表的学科分类字段
--   - adjustments 历年调剂信息表
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. 扩展 majors 表 — 增加学科分类字段（用于"按专业分类"功能）
-- ---------------------------------------------------------------------------
ALTER TABLE public.majors
  ADD COLUMN IF NOT EXISTS subject_category TEXT,   -- 13大学科门类
  ADD COLUMN IF NOT EXISTS first_discipline  TEXT;  -- 一级学科名称

COMMENT ON COLUMN public.majors.subject_category IS '13大学科门类（如工学/理学/管理学）';
COMMENT ON COLUMN public.majors.first_discipline  IS '一级学科名称（如计算机科学与技术）';

CREATE INDEX IF NOT EXISTS idx_majors_subject_category
  ON public.majors (subject_category)
  WHERE subject_category IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 2. adjustments 历年调剂信息表
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.adjustments (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id      UUID NOT NULL REFERENCES public.schools (id) ON DELETE CASCADE,
  major_id       UUID REFERENCES public.majors (id) ON DELETE SET NULL,
  year           INT  NOT NULL,
  major_name     TEXT NOT NULL,
  quota          INT,                 -- 调剂名额
  requirements   TEXT,               -- 调剂要求
  contact        TEXT,               -- 联系方式
  url            TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (school_id, major_name, year)
);

COMMENT ON TABLE  public.adjustments             IS '历年调剂信息';
COMMENT ON COLUMN public.adjustments.quota       IS '可接收调剂人数（NULL 表示未知）';
COMMENT ON COLUMN public.adjustments.requirements IS '调剂要求文字说明';

CREATE INDEX IF NOT EXISTS idx_adjustments_school_id
  ON public.adjustments (school_id);

CREATE INDEX IF NOT EXISTS idx_adjustments_year
  ON public.adjustments (school_id, year DESC);

-- ---------------------------------------------------------------------------
-- 3. RLS
-- ---------------------------------------------------------------------------
ALTER TABLE public.adjustments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "adjustments are viewable by everyone"
  ON public.adjustments FOR SELECT USING (true);
