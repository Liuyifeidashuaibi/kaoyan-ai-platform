import type { Metadata } from "next";

import { AdminModulePage } from "@/components/admin/layout/admin-module-page";
import { adminNavItems } from "@/config/admin-navigation";

const nav = adminNavItems.find((item) => item.id === "settings")!;

export const metadata: Metadata = { title: "角色权限" };

export default function AdminSettingsRolesPage() {
  return (
    <AdminModulePage title="角色权限" subNav={nav.children}>
      <div className="rounded-xl border border-border/60 bg-card p-6 text-sm text-muted-foreground">
        当前通过 <code className="rounded bg-muted px-1">ADMIN_EMAILS</code>{" "}
        环境变量控制管理员白名单。后续可扩展 Supabase 角色表与 RLS 策略。
      </div>
    </AdminModulePage>
  );
}
