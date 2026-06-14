import { UserProfileClient } from "@/components/community/user-profile-client";

interface PageProps {
  params: Promise<{ userId: string }>;
}

export default async function UserProfilePage({ params }: PageProps) {
  const { userId } = await params;
  return <UserProfileClient userId={userId} />;
}
