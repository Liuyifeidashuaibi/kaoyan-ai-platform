import dynamic from "next/dynamic";
import { requireAuth } from "@/lib/auth/require-auth";

const SettingsPageClient = dynamic(
  () =>
    import("@/components/settings/settings-page-client").then(
      (mod) => mod.SettingsPageClient
    ),
  {
    loading: () => (
      <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
        Loading settings…
      </div>
    ),
  }
);

export default async function SettingsPage() {
  await requireAuth("/settings");

  return (
    <div className="flex flex-col gap-6 p-6 md:p-8">
      <SettingsPageClient />
    </div>
  );
}
