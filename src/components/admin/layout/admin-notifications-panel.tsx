"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Bell } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { fetchDashboardActivity, type ActivityItem } from "@/lib/admin/api/dashboard";
import { cn } from "@/lib/utils";

const SEEN_KEY = "admin-notifications-seen-at";

function formatRelativeTime(iso: string) {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "刚刚";
    if (mins < 60) return `${mins} 分钟前`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours} 小时前`;
    return new Date(iso).toLocaleDateString("zh-CN");
  } catch {
    return iso;
  }
}

const typeLabel: Record<ActivityItem["type"], string> = {
  user: "用户",
  post: "社区",
  agent: "Agent",
  sync: "同步",
  report: "举报",
};

export function AdminNotificationsPanel() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [unread, setUnread] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchDashboardActivity(12);
      const list = data ?? [];
      setItems(list);
      const seenAt = Number(localStorage.getItem(SEEN_KEY) || 0);
      const count = list.filter((item) => new Date(item.time).getTime() > seenAt).length;
      setUnread(count);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 60_000);
    return () => window.clearInterval(timer);
  }, [load]);

  function markSeen() {
    localStorage.setItem(SEEN_KEY, String(Date.now()));
    setUnread(0);
  }

  return (
    <DropdownMenu
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) void load();
        else markSeen();
      }}
    >
      <DropdownMenuTrigger
        render={
          <Button variant="ghost" size="icon-sm" aria-label="通知">
            <span className="relative">
              <Bell className="size-4" />
              {unread > 0 ? (
                <span className="absolute -right-1 -top-1 flex size-4 items-center justify-center rounded-full bg-amber-500 text-[10px] font-medium text-white">
                  {unread > 9 ? "9+" : unread}
                </span>
              ) : null}
            </span>
          </Button>
        }
      />
      <DropdownMenuContent align="end" className="w-80 p-0">
        <div className="flex items-center justify-between border-b border-border/60 px-4 py-3">
          <p className="text-sm font-medium">通知</p>
          <Link
            href="/admin/dashboard"
            className="text-xs text-muted-foreground hover:text-foreground"
            onClick={() => setOpen(false)}
          >
            查看全部
          </Link>
        </div>
        <div className="max-h-80 overflow-y-auto">
          {loading && items.length === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-muted-foreground">加载中…</p>
          ) : items.length === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-muted-foreground">暂无新通知</p>
          ) : (
            <ul className="divide-y divide-border/60">
              {items.map((item) => (
                <li key={item.id}>
                  {item.href ? (
                    <Link
                      href={item.href}
                      className="flex gap-3 px-4 py-3 transition-colors hover:bg-muted/50"
                      onClick={() => setOpen(false)}
                    >
                      <NotificationRow item={item} />
                    </Link>
                  ) : (
                    <div className="flex gap-3 px-4 py-3">
                      <NotificationRow item={item} />
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function NotificationRow({ item }: { item: ActivityItem }) {
  return (
    <>
      <Badge variant="outline" className="mt-0.5 h-5 shrink-0 font-normal">
        {typeLabel[item.type]}
      </Badge>
      <div className="min-w-0 flex-1">
        <p className={cn("text-sm leading-snug", item.type === "report" && "text-amber-700")}>
          {item.message}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">{formatRelativeTime(item.time)}</p>
      </div>
    </>
  );
}
