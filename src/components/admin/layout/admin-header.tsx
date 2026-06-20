"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

import { AdminMobileNav } from "@/components/admin/layout/admin-mobile-nav";
import { getAdminBreadcrumbs } from "@/config/admin-navigation";
import { AdminNotificationsPanel } from "@/components/admin/layout/admin-notifications-panel";
import { AdminBreadcrumb } from "@/components/admin/layout/admin-breadcrumb";
import { AdminCommandMenu } from "@/components/admin/layout/admin-command-menu";
import { AdminUserBadge } from "@/components/admin/layout/admin-user-badge";
import { cn } from "@/lib/utils";

export function AdminHeader({ className }: { className?: string }) {
  const pathname = usePathname();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const breadcrumbs = getAdminBreadcrumbs(pathname);

  return (
    <header
      className={cn(
        "sticky top-0 z-10 flex h-14 shrink-0 items-center justify-between border-b border-border/60 bg-background/80 px-6 backdrop-blur-md",
        className
      )}
    >
      {mounted ? (
        <AdminBreadcrumb items={breadcrumbs} className="min-w-0 flex-1 truncate" />
      ) : (
        <div className="h-4 w-40 animate-pulse rounded bg-muted/60" />
      )}

      <div className="flex items-center gap-2">
        <AdminMobileNav />
        <AdminCommandMenu />
        <AdminNotificationsPanel />
        <AdminUserBadge />
      </div>
    </header>
  );
}
