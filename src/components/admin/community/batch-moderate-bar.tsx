"use client";

import { useState } from "react";

import { useAdminToast } from "@/components/admin/shared/admin-toast";
import { Button } from "@/components/ui/button";
import { batchModeratePosts, type PostModerateAction } from "@/lib/admin/api/community";

export function BatchModerateBar({
  selectedIds,
  onClear,
  onDone,
}: {
  selectedIds: string[];
  onClear: () => void;
  onDone: () => void;
}) {
  const { toast } = useAdminToast();
  const [loading, setLoading] = useState(false);

  if (selectedIds.length === 0) return null;

  async function run(action: PostModerateAction) {
    setLoading(true);
    try {
      const res = await batchModeratePosts(selectedIds, action);
      toast(`已处理 ${res?.success.length ?? 0} 条`, "success");
      onClear();
      onDone();
    } catch (e) {
      toast(e instanceof Error ? e.message : "批量操作失败", "error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border/60 bg-muted/40 px-4 py-2 text-sm">
      <span className="text-muted-foreground">已选 {selectedIds.length} 项</span>
      <Button size="sm" variant="outline" disabled={loading} onClick={() => void run("hide")}>
        批量隐藏
      </Button>
      <Button size="sm" variant="outline" disabled={loading} onClick={() => void run("show")}>
        批量恢复
      </Button>
      <Button size="sm" variant="ghost" disabled={loading} onClick={onClear}>
        取消
      </Button>
    </div>
  );
}
