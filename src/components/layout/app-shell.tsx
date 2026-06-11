import { AppHeader } from "@/components/layout/app-header";
import { AppSidebar } from "@/components/layout/app-sidebar";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full flex-col">
      <AppHeader />
      <div className="flex flex-1 min-h-0">
        <AppSidebar />
        <main className="flex-1 min-h-0 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
