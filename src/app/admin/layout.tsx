import type { Metadata } from "next";

import { AdminShell } from "@/components/admin/layout/admin-shell";

export const metadata: Metadata = {
  title: {
    default: "运营台",
    template: "%s · 运营台",
  },
  description: "PNIXPG 管理后台",
};

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <AdminShell>{children}</AdminShell>
    </div>
  );
}
