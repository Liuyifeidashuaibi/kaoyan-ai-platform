"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import type { AdminSubNavItem } from "@/config/admin-navigation";
import { cn } from "@/lib/utils";

export function AdminSubNav({ items }: { items: AdminSubNavItem[] }) {
  const pathname = usePathname();

  return (
    <nav className="flex flex-wrap gap-1 border-b border-border/60 pb-px">
      {items.map((item) => {
        const isActive =
          pathname === item.href ||
          (item.href !== items[0]?.href && pathname.startsWith(`${item.href}/`));

        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "relative px-3 py-2 text-sm transition-colors",
              isActive
                ? "font-medium text-foreground"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {item.label}
            {isActive ? (
              <span className="absolute inset-x-3 -bottom-px h-px bg-foreground" />
            ) : null}
          </Link>
        );
      })}
    </nav>
  );
}
