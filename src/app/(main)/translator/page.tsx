import dynamic from "next/dynamic";
import { requireAuth } from "@/lib/auth/require-auth";

const TranslatorPageClient = dynamic(
  () =>
    import("./_components/translator-page-client").then(
      (mod) => mod.TranslatorPageClient
    ),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Loading translator…
      </div>
    ),
  }
);

export default async function TranslatorPage() {
  await requireAuth("/translator");
  return <TranslatorPageClient />;
}
