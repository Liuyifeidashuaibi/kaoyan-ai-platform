import { cn } from "@/lib/utils";

export function AdminContent({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mx-auto w-full max-w-[1400px] flex-1 px-6 py-8", className)}>
      {children}
    </div>
  );
}
