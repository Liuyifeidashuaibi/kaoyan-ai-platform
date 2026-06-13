import { cn } from "@/lib/utils";
import { getUniversityLevelTags, type University } from "@/lib/api/schools";

interface LevelTagsProps {
  university: Pick<University, "level_985" | "level_211" | "double_first_class" | "school_type">;
  className?: string;
  variant?: "default" | "light";
}

/** 浅灰底院校身份标签 */
export function LevelTags({ university, className, variant = "default" }: LevelTagsProps) {
  const tags = getUniversityLevelTags(university as University);
  const all = [...tags, university.school_type].filter(Boolean);

  if (all.length === 0) return null;

  return (
    <div className={cn("flex flex-wrap gap-1.5", className)}>
      {all.map((tag) => (
        <span
          key={tag}
          className={cn(
            "inline-flex items-center rounded-md px-2 py-0.5 text-[11px]",
            variant === "light"
              ? "bg-white/25 text-white"
              : "bg-muted text-muted-foreground"
          )}
        >
          {tag}
        </span>
      ))}
    </div>
  );
}
