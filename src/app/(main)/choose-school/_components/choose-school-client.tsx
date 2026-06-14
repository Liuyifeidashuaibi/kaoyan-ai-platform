"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { SchoolsPageClient } from "../../schools/_components/schools-page-client";

export function ChooseSchoolClient() {
  return (
    <div className="flex min-h-full flex-col bg-[#f5f6f8]">
      <div className="border-b border-orange-100 bg-gradient-to-r from-orange-500 to-orange-600 px-4 py-5 text-white lg:px-8">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-medium text-orange-100">择校数据中心</p>
            <h1 className="mt-1 text-xl font-bold lg:text-2xl">择校</h1>
          </div>
          <Link
            href="/schools?view=major"
            className="inline-flex items-center gap-1 rounded-lg bg-white/15 px-3 py-2 text-xs font-medium hover:bg-white/25"
          >
            按专业检索
            <ArrowRight className="size-3.5" />
          </Link>
        </div>
      </div>
      <div className="flex-1">
        <SchoolsPageClient basePath="/choose-school" />
      </div>
    </div>
  );
}
