"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { PanelLeft, PanelLeftClose } from "lucide-react";

import { navItems } from "@/config/navigation";
import { cn } from "@/lib/utils";

function isNavActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

const SIDEBAR_COLLAPSED_KEY = "app-sidebar-collapsed";

export function AppSidebar() {
  const pathname = usePathname();
  const [mounted, setMounted] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    setMounted(true);
    try {
      const saved = localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
      if (saved === "true") setCollapsed(true);
    } catch {}
  }, []);

  const toggleCollapsed = () => {
    const next = !collapsed;
    setCollapsed(next);
    try {
      localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next));
    } catch {}
  };

  return (
    <aside
      className={cn(
        "hidden shrink-0 border-r border-border bg-sidebar md:flex md:flex-col transition-[width] duration-200 ease-in-out",
        collapsed ? "w-14" : "w-56"
      )}
    >
      {/* Header: Logo + Brand + Toggle (one row) */}
      <div className="flex shrink-0 items-center gap-1.5 border-b border-border px-2 py-2">
        {collapsed ? (
          <button
            type="button"
            onClick={toggleCollapsed}
            className="mx-auto inline-flex size-9 items-center justify-center rounded-lg transition-colors hover:bg-sidebar-accent/60"
            aria-label="Expand sidebar"
          >
            <PanelLeft className="size-5 text-sidebar-foreground" />
          </button>
        ) : (
          <>
            <Link
              href="/"
              className="flex items-center gap-2 rounded-lg px-1 py-0.5 transition-colors hover:bg-sidebar-accent/60"
            >
              <Image
                src="/logo.png"
                alt="PNIXPG"
                width={24}
                height={24}
                className="shrink-0 rounded-md object-cover"
              />
              <span className="text-sm font-bold text-sidebar-foreground">
                PNIXPG
              </span>
            </Link>
            <button
              type="button"
              onClick={toggleCollapsed}
              className="ml-auto inline-flex size-8 items-center justify-center rounded-lg transition-colors hover:bg-sidebar-accent/60"
              aria-label="Collapse sidebar"
            >
              <PanelLeftClose className="size-4.5 text-sidebar-foreground" />
            </button>
          </>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto p-2">
        {navItems.map((item) => {
          const isActive = mounted && isNavActive(pathname, item.href);
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              title={collapsed ? item.label : undefined}
              className={cn(
                "flex items-center rounded-lg transition-colors",
                collapsed
                  ? "justify-center px-0 py-2"
                  : "gap-2.5 px-2.5 py-1.5 text-sm font-medium",
                isActive
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground"
              )}
            >
              <Icon className="size-4 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
