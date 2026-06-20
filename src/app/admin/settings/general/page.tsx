import type { Metadata } from "next";

import { AdminModulePage } from "@/components/admin/layout/admin-module-page";
import { adminNavItems } from "@/config/admin-navigation";

const nav = adminNavItems.find((item) => item.id === "settings")!;

export const metadata: Metadata = { title: "通用设置" };

export default function AdminSettingsGeneralPage() {
  return (
    <AdminModulePage
      title="通用设置"
      description="平台运营配置"
      subNav={nav.children}
    >
      <div className="space-y-4 rounded-xl border border-border/60 bg-card p-6 text-sm">
        <div>
          <p className="font-medium">管理员邮箱</p>
          <p className="mt-1 text-muted-foreground">
            通过环境变量 <code className="rounded bg-muted px-1">ADMIN_EMAILS</code>{" "}
            配置，逗号分隔。
          </p>
        </div>
        <div>
          <p className="font-medium">后端 API</p>
          <p className="mt-1 text-muted-foreground">
            Admin 接口前缀 <code className="rounded bg-muted px-1">/api/admin</code>
            ，需携带 Supabase JWT 或开发环境 Bearer dev。
          </p>
        </div>
      </div>
    </AdminModulePage>
  );
}
