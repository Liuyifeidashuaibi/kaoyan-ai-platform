import { WrongQuestionsApp } from "@/components/wrong-questions/wrong-questions-app";
import { requireAuth } from "@/lib/auth/require-auth";

type PageProps = {
  searchParams: Promise<{ folder?: string }>;
};

export default async function WrongQuestionsPage({ searchParams }: PageProps) {
  await requireAuth("/wrong-questions");
  const { folder } = await searchParams;

  return <WrongQuestionsApp initialFolder={folder?.trim() || undefined} />;
}
