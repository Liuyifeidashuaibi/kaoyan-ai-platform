import { SkeletonList } from "@/components/schools/skeleton-list";

export default function ChooseSchoolLoading() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
      <div className="mb-4 h-10 w-48 animate-pulse rounded-lg bg-muted" />
      <SkeletonList count={6} />
    </div>
  );
}
