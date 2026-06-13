"use client";

import Link from "next/link";
import { Flame } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  type UniversityWithMajorCount,
  getUniversityInitial,
  isHotUniversity,
} from "@/lib/api/schools";
import { LevelTags } from "./level-tags";

interface UniversityCardProps {
  university: UniversityWithMajorCount;
  className?: string;
  showAskButton?: boolean;
}

export function UniversityCard({
  university,
  className,
  showAskButton = true,
}: UniversityCardProps) {
  const initial = getUniversityInitial(university.name);
  const hot = isHotUniversity(university);
  const gradUrl = university.graduate_url;

  return (
    <Link
      href={`/schools/${university.id}?tab=scores`}
      className={cn(
        "group relative flex flex-col rounded-2xl bg-white p-4 shadow-sm transition-shadow hover:shadow-md",
        className
      )}
    >
      <div className="flex flex-1 gap-3">
        <div className="shrink-0">
          {university.logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={university.logo_url}
              alt={university.name}
              className="size-14 rounded-full object-cover ring-2 ring-orange-50"
            />
          ) : (
            <div className="flex size-14 items-center justify-center rounded-full bg-orange-50 ring-2 ring-orange-100">
              <span className="text-base font-bold text-orange-600">{initial}</span>
            </div>
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="mb-1.5 flex items-center gap-1.5">
            <h3 className="truncate text-base font-bold text-foreground">
              {university.name}
            </h3>
            {hot && <Flame className="size-4 shrink-0 fill-orange-500 text-orange-500" />}
          </div>
          <LevelTags university={university} />
        </div>
      </div>

      <div className="mt-4 flex items-end justify-between border-t border-border/40 pt-3">
        <div className="flex gap-6">
          <div>
            <p className="text-lg font-bold text-foreground leading-none">
              {university.major_count}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">招生专业数</p>
          </div>
          <div>
            <p className="text-lg font-bold text-foreground leading-none">
              {university.enrollment_total > 0 ? university.enrollment_total : "—"}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">招生人数</p>
          </div>
        </div>

        {showAskButton && gradUrl && (
          <span
            role="button"
            tabIndex={0}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              window.open(gradUrl, "_blank", "noopener,noreferrer");
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                e.stopPropagation();
                window.open(gradUrl, "_blank", "noopener,noreferrer");
              }
            }}
            className="shrink-0 rounded-full bg-orange-500 px-4 py-1.5 text-xs font-medium text-white transition-colors hover:bg-orange-600"
          >
            访问研究生官网
          </span>
        )}
      </div>
    </Link>
  );
}
