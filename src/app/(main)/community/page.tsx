"use client";

import dynamic from "next/dynamic";

const CommunityClient = dynamic(
  () =>
    import("@/components/community/community-client").then(
      (mod) => mod.CommunityClient
    ),
  {
    ssr: false,
    loading: () => (
      <div className="flex justify-center p-16 text-muted-foreground">加载社区…</div>
    ),
  }
);

export default function CommunityPage() {
  return <CommunityClient />;
}
