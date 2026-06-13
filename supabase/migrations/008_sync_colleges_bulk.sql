-- 从 majors.college 批量同步 colleges（幂等）
INSERT INTO public.colleges (university_id, name)
SELECT DISTINCT m.university_id, trim(m.college)
FROM public.majors m
WHERE m.college IS NOT NULL
  AND trim(m.college) <> ''
  AND trim(m.college) <> '未知学院'
ON CONFLICT (university_id, name) DO NOTHING;
