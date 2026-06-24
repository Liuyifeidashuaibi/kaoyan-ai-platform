import dynamic from "next/dynamic";
import { requireAuth } from "@/lib/auth/require-auth";

const WrongQuestionsPageClient = dynamic(
  () =>
    import("./_components/wrong-questions-page-client").then(
      (mod) => mod.WrongQuestionsPageClient
    ),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Loading…
      </div>
    ),
  }
);

type PageProps = {
  searchParams: Promise<{ folder?: string }>;
};

export default async function WrongQuestionsPage({ searchParams }: PageProps) {
  await requireAuth("/wrong-questions");
  const { folder } = await searchParams;

  return <WrongQuestionsPageClient initialFolder={folder?.trim() || undefined} />;
}
