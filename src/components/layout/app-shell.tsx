import { AppHeader } from "@/components/layout/app-header";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { PageFadeWrapper } from "@/components/layout/page-fade-wrapper";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full flex-col">
      <AppHeader />
      <div className="flex flex-1 min-h-0">
        <AppSidebar />
        <PageFadeWrapper className="flex-1 min-h-0 overflow-auto">
          {children}
        </PageFadeWrapper>
      </div>
    </div>
  );
}
