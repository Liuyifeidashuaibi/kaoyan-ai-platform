"use client";

import dynamic from "next/dynamic";

import { CommunityFeedSkeleton } from "@/components/community/community-feed-skeleton";

const CommunityClient = dynamic(
  () =>
    import("@/components/community/community-client").then(
      (mod) => mod.CommunityClient
    ),
  {
    ssr: false,
    loading: () => (
      <div className="flex flex-col gap-6 p-6 md:p-8">
        <CommunityFeedSkeleton count={5} />
      </div>
    ),
  }
);

export default function CommunityPage() {
  return <CommunityClient />;
}
