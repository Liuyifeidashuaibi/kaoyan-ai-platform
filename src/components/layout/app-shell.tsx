import { AppHeader } from "@/components/layout/app-header";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { MobileBrandMark } from "@/components/layout/mobile-brand-mark";
import { PageFadeWrapper } from "@/components/layout/page-fade-wrapper";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full flex-col">
      <AppHeader />
      <div className="flex min-h-0 flex-1">
        <AppSidebar />
        <PageFadeWrapper className="min-h-0 flex-1 overflow-y-auto pb-16 md:pb-0">
          {children}
        </PageFadeWrapper>
      </div>
      <MobileBrandMark />
    </div>
  );
}
