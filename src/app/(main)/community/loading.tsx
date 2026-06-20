import { CommunityFeedSkeleton } from "@/components/community/community-feed-skeleton";

export default function CommunityLoading() {
  return (
    <div className="flex flex-col gap-6 p-6 md:p-8">
      <div className="h-8 w-40 animate-pulse rounded-lg bg-muted" />
      <div className="h-10 w-full animate-pulse rounded-lg bg-muted" />
      <CommunityFeedSkeleton count={5} />
    </div>
  );
}
