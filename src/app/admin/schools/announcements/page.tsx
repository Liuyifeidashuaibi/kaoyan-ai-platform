import type { Metadata } from "next";

import { AnnouncementsListClient } from "@/components/admin/schools/announcements-list-client";

export const metadata: Metadata = { title: "公告管理" };

export default function AdminSchoolsAnnouncementsPage() {
  return <AnnouncementsListClient />;
}
