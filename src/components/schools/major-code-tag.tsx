import { cn } from "@/lib/utils";

interface MajorCodeTagProps {
  code: string;
  className?: string;
}

/** 左白右橙拼接式专业代码标签 */
export function MajorCodeTag({ code, className }: MajorCodeTagProps) {
  return (
    <div className={cn("inline-flex shrink-0 overflow-hidden rounded-md text-xs font-medium", className)}>
      <span className="border border-orange-500 bg-white px-2 py-1 text-orange-500">
        专业代码
      </span>
      <span className="bg-orange-500 px-2.5 py-1 font-mono text-white">{code}</span>
    </div>
  );
}
