-- =============================================================================
-- 012_data_rebuild_finalize.sql — Phase 5 专业主数据批量补全
-- =============================================================================

UPDATE public.majors
SET master_type = CASE
  WHEN degree_type = '学硕' THEN '学术型'
  WHEN degree_type = '专硕' THEN '专业型'
  ELSE master_type
END
WHERE master_type IS NULL AND degree_type IS NOT NULL;

UPDATE public.majors
SET status = 'active'
WHERE status IS NULL OR trim(status) = '';

UPDATE public.majors
SET last_verified_at = now()
WHERE last_verified_at IS NULL;

-- Phase 4: 从 majors.college 文本绑定 college_id
UPDATE public.majors m
SET college_id = c.id
FROM public.colleges c
WHERE m.university_id = c.university_id
  AND trim(m.college) = c.name
  AND m.college_id IS NULL
  AND trim(coalesce(m.college, '')) <> '';

-- 删除无专业引用的 orphan colleges
DELETE FROM public.colleges c
WHERE NOT EXISTS (
  SELECT 1 FROM public.majors m WHERE m.college_id = c.id
);

UPDATE public.schools_sync_meta
SET revision = revision + 1,
    updated_at = now(),
    note = 'data_rebuild_finalize_2026-06-14';
