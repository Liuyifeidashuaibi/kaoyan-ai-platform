import dynamic from "next/dynamic";
import { requireAuth } from "@/lib/auth/require-auth";

const ProfilePanel = dynamic(
  () =>
    import("@/components/profile/profile-panel").then(
      (mod) => mod.ProfilePanel
    ),
  {
    loading: () => (
      <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
        Loading profile…
      </div>
    ),
  }
);

export default async function ProfilePage() {
  const user = await requireAuth("/profile");

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-6 md:p-8">
      <h1 className="text-2xl font-semibold tracking-tight">Profile</h1>
      <ProfilePanel
        userId={user.id}
        email={user.email}
        createdAt={user.created_at}
      />
    </div>
  );
}
