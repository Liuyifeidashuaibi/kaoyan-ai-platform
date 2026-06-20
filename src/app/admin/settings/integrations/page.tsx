import type { Metadata } from "next";

import { AdminModulePage } from "@/components/admin/layout/admin-module-page";
import { adminNavItems } from "@/config/admin-navigation";

const nav = adminNavItems.find((item) => item.id === "settings")!;

export const metadata: Metadata = { title: "第三方集成" };

export default function AdminSettingsIntegrationsPage() {
  return (
    <AdminModulePage title="第三方集成" subNav={nav.children}>
      <div className="grid gap-4 sm:grid-cols-2">
        {[
          { name: "Supabase", key: "SUPABASE_SERVICE_ROLE_KEY", desc: "数据库与鉴权" },
          { name: "DashScope", key: "DASHSCOPE_API_KEY", desc: "LLM / Embedding" },
          { name: "FastAPI", key: "BACKEND_URL", desc: "后端服务地址" },
        ].map((item) => (
          <div
            key={item.key}
            className="rounded-xl border border-border/60 bg-card p-5"
          >
            <p className="font-medium">{item.name}</p>
            <p className="mt-1 text-sm text-muted-foreground">{item.desc}</p>
            <code className="mt-3 block text-xs text-muted-foreground">{item.key}</code>
          </div>
        ))}
      </div>
    </AdminModulePage>
  );
}
