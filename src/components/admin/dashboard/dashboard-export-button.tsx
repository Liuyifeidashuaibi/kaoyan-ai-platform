"use client";

import { fetchDashboardMetrics } from "@/lib/admin/api/dashboard";
import { useAdminToast } from "@/components/admin/shared/admin-toast";
import { Button } from "@/components/ui/button";

export function DashboardExportButton() {
  const { toast } = useAdminToast();

  async function handleExport() {
    try {
      const data = await fetchDashboardMetrics();
      if (!data) {
        toast("无法获取指标数据", "error");
        return;
      }
      const rows = [
        ["指标", "数值"],
        ["总用户数", data.usersTotal],
        ["总帖子数", data.postsTotal],
        ["学校数量", data.schoolsTotal],
        ["专业数量", data.majorsTotal],
        ["今日新增用户", data.usersToday],
        ["今日新增帖子", data.postsToday],
      ];
      const csv = rows.map((r) => r.join(",")).join("\n");
      const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `dashboard-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast("报告已导出", "success");
    } catch {
      toast("导出失败", "error");
    }
  }

  return (
    <Button variant="outline" size="sm" onClick={() => void handleExport()}>
      导出报告
    </Button>
  );
}
