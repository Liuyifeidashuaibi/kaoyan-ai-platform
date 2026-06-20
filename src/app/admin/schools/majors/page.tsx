import type { Metadata } from "next";

import { MajorsListClient } from "@/components/admin/schools/majors-list-client";

export const metadata: Metadata = { title: "专业管理" };

export default function AdminSchoolsMajorsPage() {
  return <MajorsListClient />;
}
