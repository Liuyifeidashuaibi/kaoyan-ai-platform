-- 择校数据同步元信息：爬虫写入后 bump revision，前端轮询检测并刷新缓存

CREATE TABLE IF NOT EXISTS public.schools_sync_meta (
  id         INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  revision   BIGINT NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  note       TEXT
);

INSERT INTO public.schools_sync_meta (id, revision, note)
VALUES (1, 0, 'init')
ON CONFLICT (id) DO NOTHING;

COMMENT ON TABLE public.schools_sync_meta IS '择校模块数据版本号，爬虫完成后递增 revision';

ALTER TABLE public.schools_sync_meta ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'schools_sync_meta' AND policyname = 'schools_sync_meta readable'
  ) THEN
    CREATE POLICY "schools_sync_meta readable"
      ON public.schools_sync_meta FOR SELECT USING (true);
  END IF;
END $$;
