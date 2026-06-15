"use client";

import { SchoolsPageClient } from "../../schools/_components/schools-page-client";

export function ChooseSchoolClient() {
  return (
    <div className="flex min-h-full flex-col bg-white text-[#111827]">
      <SchoolsPageClient basePath="/choose-school" />
    </div>
  );
}
