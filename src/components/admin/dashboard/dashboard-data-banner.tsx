import { AlertTriangle } from "lucide-react";

export function DashboardDataBanner({
  errors,
}: {
  errors: string[];
}) {
  if (errors.length === 0) return null;

  return (
    <div className="flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm">
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-600" />
      <div>
        <p className="font-medium text-amber-900">部分数据未能从 API 加载</p>
        <p className="mt-1 text-muted-foreground">
          {errors.join(" · ")}。下方展示的是演示数据，请确认后端已启动且已配置 Supabase。
        </p>
      </div>
    </div>
  );
}
