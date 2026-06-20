import type { Metadata } from "next";

import { PdfsListClient } from "@/components/admin/schools/pdfs-list-client";

export const metadata: Metadata = { title: "PDF 管理" };

export default function AdminSchoolsPdfsPage() {
  return <PdfsListClient />;
}
