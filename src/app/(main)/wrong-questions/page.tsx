import { WrongQuestionsApp } from "@/components/wrong-questions/wrong-questions-app";
import { requireAuth } from "@/lib/auth/require-auth";

export default async function WrongQuestionsPage() {
  await requireAuth("/wrong-questions");

  return <WrongQuestionsApp />;
}
