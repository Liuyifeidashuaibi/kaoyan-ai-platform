"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { adminNavItems } from "@/config/admin-navigation";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

const quickLinks = adminNavItems.flatMap((item) => [
  { label: item.label, href: item.href, group: "导航" },
  ...(item.children?.map((c) => ({
    label: c.label,
    href: c.href,
    group: item.label,
  })) ?? []),
]);

export function AdminCommandMenu() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const router = useRouter();

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const filtered = quickLinks.filter((link) =>
    link.label.toLowerCase().includes(q.trim().toLowerCase())
  );

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="hidden items-center gap-2 rounded-lg border border-border/60 px-2.5 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted sm:inline-flex"
      >
        <span>⌘K</span>
        <span className="hidden md:inline">搜索</span>
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="gap-0 p-0 sm:max-w-lg">
          <DialogHeader className="border-b border-border/60 p-4 pb-3">
            <DialogTitle className="sr-only">命令面板</DialogTitle>
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="跳转到页面…"
              autoFocus
            />
          </DialogHeader>
          <div className="max-h-72 overflow-y-auto p-2">
            {filtered.length === 0 ? (
              <p className="px-2 py-6 text-center text-sm text-muted-foreground">
                无匹配结果
              </p>
            ) : (
              filtered.map((link) => (
                <button
                  key={link.href + link.label}
                  type="button"
                  className={cn(
                    "flex w-full flex-col items-start rounded-lg px-3 py-2 text-left text-sm hover:bg-muted"
                  )}
                  onClick={() => {
                    setOpen(false);
                    router.push(link.href);
                  }}
                >
                  <span>{link.label}</span>
                  <span className="text-xs text-muted-foreground">{link.group}</span>
                </button>
              ))
            )}
          </div>
          <div className="border-t border-border/60 px-4 py-2 text-xs text-muted-foreground">
            <Link href="/admin/agents" onClick={() => setOpen(false)}>
              打开 Agent 控制中心 →
            </Link>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
