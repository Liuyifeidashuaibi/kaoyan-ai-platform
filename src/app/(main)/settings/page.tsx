import { SettingsPageClient } from "@/components/settings/settings-page-client";
import { requireAuth } from "@/lib/auth/require-auth";

export default async function SettingsPage() {
  await requireAuth("/settings");

  return (
    <div className="flex flex-col gap-6 p-6 md:p-8">
      <SettingsPageClient />
    </div>
  );
}
