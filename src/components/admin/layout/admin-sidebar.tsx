"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowUpRight, PanelLeft, PanelLeftClose } from "lucide-react";

import { AdminNavLinks } from "@/components/admin/layout/admin-nav-links";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

const SIDEBAR_COLLAPSED_KEY = "admin-sidebar-collapsed";

export function AdminSidebar() {
  const [mounted, setMounted] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    setMounted(true);
    const stored = localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
    if (stored === "true") setCollapsed(true);
  }, []);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next));
      return next;
    });
  }

  if (!mounted) {
    return (
      <aside className="hidden w-[240px] shrink-0 border-r border-border/60 bg-[var(--admin-sidebar)] md:block">
        <div className="h-14 border-b border-border/60" />
        <div className="space-y-2 p-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-9 animate-pulse rounded-lg bg-muted/60" />
          ))}
        </div>
      </aside>
    );
  }

  return (
    <aside
      className={cn(
        "hidden shrink-0 flex-col border-r border-border/60 bg-[var(--admin-sidebar)] transition-[width] duration-200 md:flex",
        collapsed ? "w-[68px]" : "w-[240px]"
      )}
    >
      <div
        className={cn(
          "flex h-14 items-center border-b border-border/60",
          collapsed ? "flex-col justify-center gap-1 px-1 py-2" : "justify-between px-4"
        )}
      >
        {!collapsed ? (
          <div className="min-w-0">
            <p className="truncate text-sm font-medium tracking-tight">考研运营台</p>
            <p className="truncate text-[11px] text-muted-foreground">Admin</p>
          </div>
        ) : (
          <div className="flex size-8 items-center justify-center rounded-lg bg-foreground text-background text-xs font-semibold">
            K
          </div>
        )}
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={toggleCollapsed}
          aria-label={collapsed ? "展开侧边栏" : "收起侧边栏"}
        >
          {collapsed ? <PanelLeft className="size-4" /> : <PanelLeftClose className="size-4" />}
        </Button>
      </div>

      <div className="flex flex-1 flex-col">
        <AdminNavLinks collapsed={collapsed} />
      </div>

      <div className="p-3">
        <Separator className="mb-3" />
        <Link
          href="/"
          className={cn(
            "flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground",
            collapsed && "justify-center px-2"
          )}
        >
          <ArrowUpRight className="size-4 shrink-0" />
          {!collapsed ? <span>返回用户端</span> : null}
        </Link>
      </div>
    </aside>
  );
}
