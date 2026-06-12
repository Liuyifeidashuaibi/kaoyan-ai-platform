import { SchoolsFilterProvider } from "./_context/schools-filter-context";
import { SchoolsPageClient } from "./_components/schools-page-client";

export default function SchoolsPage() {
  return (
    <SchoolsFilterProvider>
      <SchoolsPageClient />
    </SchoolsFilterProvider>
  );
}
