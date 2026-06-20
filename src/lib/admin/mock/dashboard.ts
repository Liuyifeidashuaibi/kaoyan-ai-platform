/** Dashboard 静态占位数据 — 后续对接 /api/admin/dashboard */

export const dashboardMetrics = [
  { label: "总用户数", value: "12,480", delta: "较昨日 +2.1%", deltaTrend: "up" as const },
  { label: "总帖子数", value: "3,291", delta: "较昨日 +0.8%", deltaTrend: "up" as const },
  { label: "学校数量", value: "486", delta: "—", deltaTrend: "neutral" as const },
  { label: "专业数量", value: "8,102", delta: "本周 +12", deltaTrend: "up" as const },
  { label: "今日新增用户", value: "42", delta: "较均值 +5", deltaTrend: "up" as const },
  { label: "今日新增帖子", value: "18", delta: "较均值 -2", deltaTrend: "down" as const },
];

export const dashboardAgents = [
  {
    id: "sync",
    name: "SyncAgent",
    status: "running" as const,
    lastRun: "3 分钟前",
    successRate: "98.2%",
    taskCount: 24,
    pulse: true,
  },
  {
    id: "rag",
    name: "RAGAgent",
    status: "warning" as const,
    lastRun: "12 分钟前",
    successRate: "94.5%",
    taskCount: 11,
  },
  {
    id: "report",
    name: "ReportAgent",
    status: "idle" as const,
    lastRun: "2 小时前",
    successRate: "99.1%",
    taskCount: 3,
  },
];

export const dashboardActivity = [
  {
    id: "1",
    type: "user" as const,
    message: "新用户注册：张同学",
    time: "2 分钟前",
    href: "/admin/users",
  },
  {
    id: "2",
    type: "post" as const,
    message: "社区新帖待审核：《浙大计算机复试经验》",
    time: "8 分钟前",
    href: "/admin/community/moderation",
  },
  {
    id: "3",
    type: "sync" as const,
    message: "浙江大学专业数据同步完成",
    time: "15 分钟前",
    href: "/admin/schools/sync-logs",
  },
  {
    id: "4",
    type: "agent" as const,
    message: "SyncAgent 任务 #1840 执行失败",
    time: "22 分钟前",
    href: "/admin/agents",
  },
  {
    id: "5",
    type: "report" as const,
    message: "收到 1 条新举报",
    time: "35 分钟前",
    href: "/admin/community/reports",
  },
];
