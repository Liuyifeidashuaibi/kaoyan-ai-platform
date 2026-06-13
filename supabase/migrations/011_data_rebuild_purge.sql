-- =============================================================================
-- 011_data_rebuild_purge.sql — 第三阶段：删除不可信历史招生数据
-- 保留 universities / colleges / majors 基础资产
-- =============================================================================

-- 分数线（97% 来自第三方 kaoyan.cn，无官方来源）
DELETE FROM public.scores;

-- 历史公告 / 推免 / 调剂（无 verify_status / 原始文件归档）
DELETE FROM public.announcements;
DELETE FROM public.recommendations;
DELETE FROM public.adjustments;

-- 重建前拟录取记录（不符合 verify_status 规范，从今天起重新采集）
DELETE FROM public.admission_records;

-- 统计层（含报录比/录取率等不可信指标）
DELETE FROM public.major_statistics;

-- 年度统计新表（如有残留）
DELETE FROM public.major_year_stats;

-- 清空失败爬虫任务（保留表结构，监控从今天重启）
DELETE FROM public.crawl_tasks;

-- 重置来源页状态（保留 URL 注册，清除旧 hash 以便重新巡检）
UPDATE public.source_pages
SET content_hash = NULL, status = 'pending', last_fetch_time = NULL;

-- bump 前端缓存版本
UPDATE public.schools_sync_meta
SET revision = revision + 1,
    updated_at = now(),
    note = 'data_rebuild_purge_2026-06-14';
