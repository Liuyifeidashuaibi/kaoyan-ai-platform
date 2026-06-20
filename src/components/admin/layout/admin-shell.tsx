import { AdminToastProvider } from "@/components/admin/shared/admin-toast";
import { AdminContent } from "@/components/admin/layout/admin-content";
import { AdminHeader } from "@/components/admin/layout/admin-header";
import { AdminSidebar } from "@/components/admin/layout/admin-sidebar";

export function AdminShell({ children }: { children: React.ReactNode }) {
  return (
    <AdminToastProvider>
      <div className="admin-theme flex h-full min-h-0 bg-[var(--admin-surface)]">
        <AdminSidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <AdminHeader />
          <main className="min-h-0 flex-1 overflow-auto">{children}</main>
        </div>
      </div>
    </AdminToastProvider>
  );
}

export function AdminPage({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <AdminContent className={className}>{children}</AdminContent>;
}
