"use client";

import { useState } from "react";
import { Menu } from "lucide-react";

import { AdminNavLinks } from "@/components/admin/layout/admin-nav-links";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent } from "@/components/ui/sheet";

export function AdminMobileNav() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button
        variant="ghost"
        size="icon-sm"
        className="md:hidden"
        onClick={() => setOpen(true)}
        aria-label="打开菜单"
      >
        <Menu className="size-5" />
      </Button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="left" className="p-0 pt-12">
          <div className="border-b border-border/60 px-4 py-3">
            <p className="text-sm font-medium">考研运营台</p>
            <p className="text-[11px] text-muted-foreground">Admin</p>
          </div>
          <AdminNavLinks onNavigate={() => setOpen(false)} />
        </SheetContent>
      </Sheet>
    </>
  );
}
