import dynamic from "next/dynamic";
import { SchoolsFilterProvider } from "../schools/_context/schools-filter-context";
import { SchoolsSyncProvider } from "../schools/_context/schools-sync-context";

const ChooseSchoolClient = dynamic(
  () =>
    import("./_components/choose-school-client").then(
      (mod) => mod.ChooseSchoolClient
    ),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Loading schools…
      </div>
    ),
  }
);

export default function ChooseSchoolPage() {
  return (
    <SchoolsFilterProvider>
      <SchoolsSyncProvider>
        <ChooseSchoolClient />
      </SchoolsSyncProvider>
    </SchoolsFilterProvider>
  );
}
