import type { AdminSubNavItem } from "@/config/admin-navigation";
import { AdminPage } from "@/components/admin/layout/admin-shell";
import { AdminPageHeader } from "@/components/admin/layout/admin-page-header";
import { AdminSubNav } from "@/components/admin/layout/admin-sub-nav";
import { AdminPlaceholder } from "@/components/admin/shared/admin-placeholder";

type AdminModulePageProps = {
  title: string;
  description?: string;
  subNav?: AdminSubNavItem[];
  placeholderTitle?: string;
  placeholderDescription?: string;
  actions?: React.ReactNode;
  children?: React.ReactNode;
};

export function AdminModulePage({
  title,
  description,
  subNav,
  placeholderTitle,
  placeholderDescription,
  actions,
  children,
}: AdminModulePageProps) {
  return (
    <AdminPage>
      <div className="space-y-6">
        <AdminPageHeader title={title} description={description} actions={actions} />
        {subNav?.length ? <AdminSubNav items={subNav} /> : null}
        {children ?? (
          <AdminPlaceholder
            title={placeholderTitle ?? title}
            description={placeholderDescription}
          />
        )}
      </div>
    </AdminPage>
  );
}
