import { ProfilePanel } from "@/components/profile/profile-panel";
import { requireAuth } from "@/lib/auth/require-auth";

export default async function ProfilePage() {
  const user = await requireAuth("/profile");

  return (
    <div className="flex flex-col gap-6 p-6 md:p-8">
      <h1 className="text-2xl font-semibold tracking-tight">Profile</h1>
      <ProfilePanel
        userId={user.id}
        email={user.email}
        createdAt={user.created_at}
      />
    </div>
  );
}
