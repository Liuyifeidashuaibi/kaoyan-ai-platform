import { cn } from "@/lib/utils";

export function AdminDataTableShell({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-xl border border-border/60 bg-card",
        className
      )}
    >
      {children}
    </div>
  );
}

export function AdminTableFooter({
  total,
  page,
  pageSize,
  onPageChange,
}: {
  total: number;
  page: number;
  pageSize: number;
  onPageChange?: (page: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="flex items-center justify-between border-t border-border/60 px-4 py-3 text-xs text-muted-foreground">
      <span>
        共 {total} 条 · 第 {page} / {totalPages} 页
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => onPageChange?.(page - 1)}
          className="rounded-md px-2 py-1 hover:bg-muted disabled:opacity-40"
        >
          上一页
        </button>
        <button
          type="button"
          disabled={page >= totalPages}
          onClick={() => onPageChange?.(page + 1)}
          className="rounded-md px-2 py-1 hover:bg-muted disabled:opacity-40"
        >
          下一页
        </button>
      </div>
    </div>
  );
}

export function formatAdminDate(iso: string) {
  try {
    return new Date(iso).toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
