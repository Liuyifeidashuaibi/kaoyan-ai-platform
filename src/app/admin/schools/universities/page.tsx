import type { Metadata } from "next";

import { SchoolsListClient } from "@/components/admin/schools/schools-list-client";

export const metadata: Metadata = { title: "学校管理" };

export default function AdminSchoolsUniversitiesPage() {
  return <SchoolsListClient />;
}
