import { SchoolsFilterProvider } from "./_context/schools-filter-context";
import { SchoolsSyncProvider } from "./_context/schools-sync-context";
import { SchoolsPageClient } from "./_components/schools-page-client";

export default function SchoolsPage() {
  return (
    <SchoolsFilterProvider>
      <SchoolsSyncProvider>
        <SchoolsPageClient />
      </SchoolsSyncProvider>
    </SchoolsFilterProvider>
  );
}
