import { SchoolsFilterProvider } from "../schools/_context/schools-filter-context";
import { SchoolsSyncProvider } from "../schools/_context/schools-sync-context";
import { ChooseSchoolClient } from "./_components/choose-school-client";

export default function ChooseSchoolPage() {
  return (
    <SchoolsFilterProvider>
      <SchoolsSyncProvider>
        <ChooseSchoolClient />
      </SchoolsSyncProvider>
    </SchoolsFilterProvider>
  );
}
