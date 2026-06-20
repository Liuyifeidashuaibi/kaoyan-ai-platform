import type { Metadata } from "next";

import { CollegesListClient } from "@/components/admin/schools/colleges-list-client";

export const metadata: Metadata = { title: "学院管理" };

export default function AdminSchoolsCollegesPage() {
  return <CollegesListClient />;
}
