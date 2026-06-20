import type { Metadata } from "next";

import { AdminModulePage } from "@/components/admin/layout/admin-module-page";
import { adminNavItems } from "@/config/admin-navigation";

const nav = adminNavItems.find((item) => item.id === "settings")!;

export const metadata: Metadata = { title: "系统设置" };

export default function AdminSettingsPage() {
  return (
    <AdminModulePage
      title="系统设置"
      description="通用配置、角色权限与第三方集成"
      subNav={nav.children}
    >
      <div className="grid gap-4 sm:grid-cols-3">
        {[
          { title: "通用设置", href: "/admin/settings/general", desc: "平台与 Admin 配置说明" },
          { title: "角色权限", href: "/admin/settings/roles", desc: "管理员与运营角色" },
          { title: "第三方集成", href: "/admin/settings/integrations", desc: "Supabase / LLM / 爬虫" },
        ].map((item) => (
          <a
            key={item.href}
            href={item.href}
            className="rounded-xl border border-border/60 bg-card p-5 transition-colors hover:border-border"
          >
            <p className="font-medium">{item.title}</p>
            <p className="mt-2 text-sm text-muted-foreground">{item.desc}</p>
          </a>
        ))}
      </div>
    </AdminModulePage>
  );
}
