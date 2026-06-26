import { requireAuth } from "@/lib/auth/require-auth";
import { TranslatorPageClient } from "./_components/translator-page-client";

export default async function TranslatorPage() {
  await requireAuth("/translator");
  return <TranslatorPageClient />;
}
