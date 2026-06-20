-- Admin 发帖统计聚合（避免全表拉取到应用层）
CREATE OR REPLACE FUNCTION public.admin_author_post_stats(p_limit int, p_offset int)
RETURNS json
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  WITH stats AS (
    SELECT author_id, COUNT(*)::bigint AS post_count
    FROM community_posts
    WHERE deleted_at IS NULL AND author_id IS NOT NULL
    GROUP BY author_id
  ),
  ranked AS (
    SELECT author_id, post_count
    FROM stats
    ORDER BY post_count DESC, author_id
  ),
  page_rows AS (
    SELECT author_id, post_count
    FROM ranked
    LIMIT GREATEST(p_limit, 1)
    OFFSET GREATEST(p_offset, 0)
  )
  SELECT json_build_object(
    'total', (SELECT COUNT(*)::int FROM stats),
    'items', COALESCE(
      (
        SELECT json_agg(
          json_build_object('author_id', author_id, 'post_count', post_count)
          ORDER BY post_count DESC
        )
        FROM page_rows
      ),
      '[]'::json
    )
  );
$$;

COMMENT ON FUNCTION public.admin_author_post_stats IS '管理后台：按作者聚合发帖数（分页）';

GRANT EXECUTE ON FUNCTION public.admin_author_post_stats(int, int) TO service_role;
