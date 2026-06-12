"use client";

import { use } from "react";
import { SchoolsFilterProvider } from "../_context/schools-filter-context";
import { UniversityDetailClient } from "./_components/university-detail-client";

interface PageProps {
  params: Promise<{ universityId: string }>;
}

export default function UniversityDetailPage({ params }: PageProps) {
  const { universityId } = use(params);
  return (
    <SchoolsFilterProvider>
      <UniversityDetailClient universityId={universityId} />
    </SchoolsFilterProvider>
  );
}
