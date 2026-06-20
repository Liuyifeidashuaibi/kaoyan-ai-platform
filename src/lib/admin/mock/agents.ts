export const agentQuickChips = [
  { label: "同步浙江大学专业", risk: "medium" as const },
  { label: "同步全部985高校专业", risk: "high" as const },
  { label: "检查重复专业", risk: "low" as const },
  { label: "同步招生公告", risk: "medium" as const },
  { label: "生成运营周报", risk: "low" as const },
];

export const agentTasks = [
  {
    id: "1842",
    title: "同步浙江大学专业",
    status: "running" as const,
    statusLabel: "运行中",
    meta: "Task #1842 · SyncAgent",
    time: "2m 12s",
    progress: 67,
  },
  {
    id: "1840",
    title: "检查重复专业",
    status: "failed" as const,
    statusLabel: "失败",
    meta: "Task #1840 · SyncAgent · 超时",
    time: "10m 前",
  },
  {
    id: "1835",
    title: "生成运营周报",
    status: "done" as const,
    statusLabel: "已完成",
    meta: "Task #1835 · ReportAgent",
    time: "1h 前",
  },
];
