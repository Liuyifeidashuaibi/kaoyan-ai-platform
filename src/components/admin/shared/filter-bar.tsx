"use client";

import { Search } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type FilterBarProps = {
  value: string;
  onChange: (value: string) => void;
  onSearch?: () => void;
  placeholder?: string;
  actions?: React.ReactNode;
  className?: string;
};

export function FilterBar({
  value,
  onChange,
  onSearch,
  placeholder = "搜索…",
  actions,
  className,
}: FilterBarProps) {
  return (
    <div className={cn("flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between", className)}>
      <div className="relative max-w-sm flex-1">
        <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onSearch?.()}
          placeholder={placeholder}
          className="pl-8"
        />
      </div>
      <div className="flex items-center gap-2">
        {onSearch ? (
          <Button variant="outline" size="sm" onClick={onSearch}>
            搜索
          </Button>
        ) : null}
        {actions}
      </div>
    </div>
  );
}
