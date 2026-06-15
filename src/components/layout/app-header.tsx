"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { UserBadge } from "@/components/layout/user-badge";
import { navItems } from "@/config/navigation";
import { cn } from "@/lib/utils";

function isNavActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppHeader() {
  const pathname = usePathname();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="flex h-14 items-center gap-4 px-4 md:px-6">
        <Link href="/" className="flex items-center gap-2 font-semibold text-[#111827]">
          <Image
            src="/logo.png"
            alt="考研 AI 平台"
            width={32}
            height={32}
            className="size-8 rounded-lg object-cover"
            priority
          />
          <span className="hidden sm:inline">考研 AI 平台</span>
        </Link>

        <nav className="flex flex-1 items-center gap-1 overflow-x-auto md:hidden">
          {navItems.map((item) => {
            const isActive = mounted && isNavActive(pathname, item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "shrink-0 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors",
                  isActive
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto shrink-0">
          <UserBadge />
        </div>
      </div>
    </header>
  );
}
