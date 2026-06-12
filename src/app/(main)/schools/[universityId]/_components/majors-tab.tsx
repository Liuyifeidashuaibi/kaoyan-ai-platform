"use client";

import { useState } from "react";
import { ChevronDown, Search, X } from "lucide-react";
import { BottomFilterSheet } from "@/components/schools/bottom-filter-sheet";
import { EmptyState } from "@/components/schools/empty-state";
import { SkeletonList } from "@/components/schools/skeleton-list";
import { cn } from "@/lib/utils";
import type { Major } from "@/lib/api/schools";

interface MajorsTabProps {
  majors: Major[];
}

export function MajorsTab({ majors }: MajorsTabProps) {
  const [studyMode, setStudyMode] = useState("");
  const [degreeType, setDegreeType] = useState("");
  const [search, setSearch] = useState("");
  const [openSheet, setOpenSheet] = useState<"studyMode" | "degree" | null>(null);

  const filtered = majors.filter((m) => {
    if (studyMode && m.study_mode !== studyMode) return false;
    if (degreeType && m.degree_type !== degreeType) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      return (
        m.name.toLowerCase().includes(q) ||
        (m.code ?? "").toLowerCase().includes(q) ||
        (m.college ?? "").toLowerCase().includes(q)
      );
    }
    return true;
  });

  const byCollege: Record<string, Major[]> = {};
  for (const m of filtered) {
    const col = m.college ?? "其他";
    (byCollege[col] ??= []).push(m);
  }

  return (
    <div className="flex flex-col h-full">
      {/* 筛选栏 */}
      <div className="bg-background border-b border-border px-4 py-2.5 flex items-center gap-2">
        <FilterChip
          label={studyMode || "学习方式"}
          active={!!studyMode}
          onClick={() => setOpenSheet("studyMode")}
        />
        <FilterChip
          label={degreeType || "学位类别"}
          active={!!degreeType}
          onClick={() => setOpenSheet("degree")}
        />
        <div className="ml-auto flex items-center gap-1.5 rounded-lg border border-border bg-background px-2 py-1.5">
          <Search className="size-3.5 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索专业"
            className="w-20 bg-transparent text-xs outline-none placeholder:text-muted-foreground"
          />
          {search && (
            <button onClick={() => setSearch("")}>
              <X className="size-3 text-muted-foreground" />
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {majors.length === 0 ? (
          <SkeletonList count={6} className="rounded-none" />
        ) : filtered.length === 0 ? (
          <EmptyState title="没有匹配专业" description="调整筛选条件或清除搜索" />
        ) : (
          <div className="pb-8 bg-card">
            {Object.entries(byCollege).map(([college, items]) => (
              <CollegeGroup key={college} college={college} majors={items} />
            ))}
          </div>
        )}
      </div>

      <BottomFilterSheet
        open={openSheet === "studyMode"}
        onClose={() => setOpenSheet(null)}
        title="学习方式"
        options={[
          { value: "全日制", label: "全日制" },
          { value: "非全日制", label: "非全日制" },
        ]}
        selected={studyMode}
        onSelect={setStudyMode}
      />
      <BottomFilterSheet
        open={openSheet === "degree"}
        onClose={() => setOpenSheet(null)}
        title="学位类别"
        options={[
          { value: "学硕", label: "学硕" },
          { value: "专硕", label: "专硕" },
        ]}
        selected={degreeType}
        onSelect={setDegreeType}
      />
    </div>
  );
}

function CollegeGroup({ college, majors }: { college: string; majors: Major[] }) {
  const [expanded, setExpanded] = useState(true);
  return (
    <div>
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between border-b border-border/60 bg-muted/30 px-4 py-2.5"
      >
        <span className="text-xs font-semibold text-foreground">{college}</span>
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <span>{majors.length}个专业</span>
          <ChevronDown className={cn("size-3.5 transition-transform", expanded && "rotate-180")} />
        </div>
      </button>
      {expanded && (
        <div>
          {majors.map((m) => (
            <MajorRow key={m.id} major={m} />
          ))}
        </div>
      )}
    </div>
  );
}

function MajorRow({ major }: { major: Major }) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 border-b border-border/60 last:border-0">
      <span className="font-mono text-xs text-muted-foreground w-14 shrink-0">{major.code}</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm truncate">{major.name}</p>
        <p className="text-xs text-muted-foreground mt-0.5">
          {[major.study_mode, major.exam_type].filter(Boolean).join(" · ")}
          {major.enrollment_count ? ` · 招${major.enrollment_count}人` : ""}
        </p>
      </div>
      <span
        className={cn(
          "shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium border",
          major.degree_type === "专硕"
            ? "bg-blue-50 text-blue-700 border-blue-100"
            : "bg-green-50 text-green-700 border-green-100"
        )}
      >
        {major.degree_type ?? "学硕"}
      </span>
    </div>
  );
}

function FilterChip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center gap-0.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors",
        active
          ? "border-orange-300 bg-orange-50 text-orange-600"
          : "border-border bg-background text-muted-foreground"
      )}
    >
      {label}
      <ChevronDown className="size-3" />
    </button>
  );
}
