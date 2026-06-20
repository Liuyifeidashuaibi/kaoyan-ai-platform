"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { adminNavItems, isAdminNavItemActive } from "@/config/admin-navigation";
import { StatusDot } from "@/components/admin/shared/status-dot";
import { cn } from "@/lib/utils";

export function AdminNavLinks({
  onNavigate,
  collapsed,
}: {
  onNavigate?: () => void;
  collapsed?: boolean;
}) {
  const pathname = usePathname();

  return (
    <nav className="flex flex-col gap-0.5 p-3">
      {adminNavItems.map((item) => {
        const isActive = isAdminNavItemActive(pathname, item);
        const Icon = item.icon;
        return (
          <Link
            key={item.id}
            href={item.href}
            onClick={onNavigate}
            className={cn(
              "relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              collapsed && "justify-center px-2",
              isActive
                ? "bg-muted text-foreground"
                : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
            )}
          >
            {isActive && !collapsed ? (
              <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-foreground" />
            ) : null}
            <Icon className="size-4 shrink-0" />
            {!collapsed ? <span>{item.label}</span> : null}
            {!collapsed && item.badge === "dot" ? (
              <StatusDot variant="running" pulse className="ml-auto" />
            ) : null}
          </Link>
        );
      })}
    </nav>
  );
}
