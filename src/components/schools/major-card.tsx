"use client";



import Link from "next/link";

import { cn } from "@/lib/utils";

import { type AggregatedMajor, formatMajorPath } from "@/lib/api/schools";

import { MajorCodeTag } from "./major-code-tag";



interface MajorCardProps {

  major: AggregatedMajor;

  className?: string;

}



export function MajorCard({ major, className }: MajorCardProps) {

  const path = formatMajorPath(major);

  const query = major.degree_type ? `?degree=${encodeURIComponent(major.degree_type)}` : "";

  const degreeLabel = major.degree_type === "专硕" ? "专业型硕士" : "学术型硕士";



  return (

    <Link

      href={`/schools/majors/${major.code}${query}`}

      className={cn(

        "flex items-center justify-between gap-4 rounded-2xl bg-white px-5 py-4 shadow-sm transition-shadow hover:shadow-md",

        className

      )}

    >

      <div className="min-w-0 flex-1">

        <div className="flex flex-wrap items-center gap-2">

          <span className="rounded-md bg-black/5 px-2 py-0.5 text-xs font-medium text-[#111827]">

            {degreeLabel}

          </span>

          <h3 className="text-lg font-bold text-foreground">{major.name}</h3>

        </div>

        <p className="mt-1 text-sm text-muted-foreground">{path}</p>

        <p className="mt-2 text-xs text-foreground">

          <span className="text-muted-foreground">开设院校：</span>

          {major.university_count} 所

          {major.total_enrollment > 0 && ` · 合计招生 ${major.total_enrollment} 人`}

        </p>

      </div>

      <MajorCodeTag code={major.code} />

    </Link>

  );

}

