"use client";

import { useState } from "react";

import { useAdminToast } from "@/components/admin/shared/admin-toast";
import { moderatePost, type PostModerateAction } from "@/lib/admin/api/community";

type PostRowActionsProps = {
  postId: string;
  isHidden: boolean;
  onDone?: () => void;
  compact?: boolean;
};

export function PostRowActions({
  postId,
  isHidden,
  onDone,
  compact,
}: PostRowActionsProps) {
  const { toast } = useAdminToast();
  const [loading, setLoading] = useState<string | null>(null);

  async function run(action: PostModerateAction, label: string) {
    if (action === "delete" && !window.confirm("确定软删除该帖子？")) return;
    setLoading(action);
    try {
      await moderatePost(postId, action);
      toast(`${label}成功`, "success");
      onDone?.();
    } catch (e) {
      toast(e instanceof Error ? e.message : `${label}失败`, "error");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className={`flex justify-end gap-1 ${compact ? "" : "min-w-[140px]"}`}>
      {isHidden ? (
        <button
          type="button"
          disabled={!!loading}
          className="rounded-md px-2 py-1 text-xs hover:bg-muted disabled:opacity-50"
          onClick={() => void run("show", "恢复")}
        >
          恢复
        </button>
      ) : (
        <button
          type="button"
          disabled={!!loading}
          className="rounded-md px-2 py-1 text-xs hover:bg-muted disabled:opacity-50"
          onClick={() => void run("hide", "隐藏")}
        >
          隐藏
        </button>
      )}
      <button
        type="button"
        disabled={!!loading}
        className="rounded-md px-2 py-1 text-xs text-destructive hover:bg-muted disabled:opacity-50"
        onClick={() => void run("delete", "删除")}
      >
        删除
      </button>
    </div>
  );
}
