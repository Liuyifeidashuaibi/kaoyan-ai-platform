import { WrongQuestionsPageClient } from "./_components/wrong-questions-page-client";
import { requireAuth } from "@/lib/auth/require-auth";

type PageProps = {
  searchParams: Promise<{ folder?: string }>;
};

export default async function WrongQuestionsPage({ searchParams }: PageProps) {
  await requireAuth("/wrong-questions");
  const { folder } = await searchParams;

  return <WrongQuestionsPageClient initialFolder={folder?.trim() || undefined} />;
}
