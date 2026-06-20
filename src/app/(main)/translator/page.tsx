import { TranslatorPageClient } from "./_components/translator-page-client";
import { requireAuth } from "@/lib/auth/require-auth";

export default async function TranslatorPage() {
  await requireAuth("/translator");
  return <TranslatorPageClient />;
}
