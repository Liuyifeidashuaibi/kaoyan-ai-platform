"use client";

import Link from "next/link";
import { MapPin, BookOpen } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  type UniversityWithMajorCount,
  getUniversityLevelTags,
  getUniversityInitial,
} from "@/lib/api/schools";

interface UniversityCardProps {
  university: UniversityWithMajorCount;
  className?: string;
}

const LEVEL_TAG_STYLE: Record<string, string> = {
  "985": "bg-orange-100 text-orange-700 border-orange-200",
  "211": "bg-blue-100 text-blue-700 border-blue-200",
  双一流A: "bg-purple-100 text-purple-700 border-purple-200",
  双一流B: "bg-violet-100 text-violet-700 border-violet-200",
  一流学科: "bg-teal-100 text-teal-700 border-teal-200",
};

export function UniversityCard({ university, className }: UniversityCardProps) {
  const tags = getUniversityLevelTags(university);
  const initial = getUniversityInitial(university.name);

  return (
    <Link
      href={`/schools/${university.id}`}
      className={cn(
        "flex items-center gap-3 px-4 py-3.5 border-b border-border",
        "last:border-0 active:bg-muted/50 transition-colors",
        className
      )}
    >
      {/* Logo / 占位符 */}
      <div className="shrink-0">
        {university.logo_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={university.logo_url}
            alt={university.name}
            className="size-12 rounded-full object-cover border border-border"
          />
        ) : (
          <div className="size-12 rounded-full bg-orange-50 border border-orange-100 flex items-center justify-center">
            <span className="text-sm font-bold text-orange-600">{initial}</span>
          </div>
        )}
      </div>

      {/* 信息 */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 mb-1">
          <span className="text-sm font-semibold text-foreground truncate">
            {university.name}
          </span>
        </div>

        {/* 标签组 */}
        {tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-1">
            {tags.map((tag) => (
              <span
                key={tag}
                className={cn(
                  "inline-flex items-center rounded px-1.5 py-px text-[10px] font-medium border",
                  LEVEL_TAG_STYLE[tag] ??
                    "bg-muted text-muted-foreground border-border"
                )}
              >
                {tag}
              </span>
            ))}
            <span className="inline-flex items-center rounded px-1.5 py-px text-[10px] font-medium border bg-muted text-muted-foreground border-border">
              {university.school_type}
            </span>
          </div>
        )}

        {/* 地区 + 专业数 */}
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-0.5">
            <MapPin className="size-3" />
            {university.province}·{university.city}
          </span>
          <span className="flex items-center gap-0.5">
            <BookOpen className="size-3" />
            {university.major_count} 个招生专业
          </span>
        </div>
      </div>

      {/* 箭头 */}
      <svg
        className="size-4 text-muted-foreground shrink-0"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
      </svg>
    </Link>
  );
}
