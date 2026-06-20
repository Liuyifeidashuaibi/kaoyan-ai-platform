"use client";

import dynamic from "next/dynamic";

const WrongQuestionsApp = dynamic(
  () =>
    import("@/components/wrong-questions/wrong-questions-app").then(
      (mod) => mod.WrongQuestionsApp
    ),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Loading notebook…
      </div>
    ),
  }
);

export function WrongQuestionsPageClient({
  initialFolder,
}: {
  initialFolder?: string;
}) {
  return <WrongQuestionsApp initialFolder={initialFolder} />;
}
