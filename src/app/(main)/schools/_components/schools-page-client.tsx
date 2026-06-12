"use client";

import { useCallback, useRef, useState } from "react";
import { SlidersHorizontal, Search, X } from "lucide-react";
import { TabNav } from "@/components/schools/tab-nav";
import { SchoolListView } from "./school-list-view";
import { MajorListView } from "./major-list-view";
import { GlobalFilterDrawer } from "./global-filter-drawer";
import { useSchoolsFilter } from "../_context/schools-filter-context";
import { cn } from "@/lib/utils";

const VIEW_TABS = [
  { value: "school", label: "按学校分类" },
  { value: "major", label: "按专业分类" },
];

export function SchoolsPageClient() {
  const { filter } = useSchoolsFilter();
  const [viewMode, setViewMode] = useState<"school" | "major">("school");
  const [filterOpen, setFilterOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [searchActive, setSearchActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const activeCount =
    [filter.level985, filter.level211, filter.doubleFirstClass].filter(Boolean)
      .length;
  const allActive = activeCount === 3;

  const handleSearchFocus = useCallback(() => setSearchActive(true), []);
  const handleSearchBlur = useCallback(() => {
    if (!search) setSearchActive(false);
  }, [search]);
  const handleClearSearch = useCallback(() => {
    setSearch("");
    setSearchActive(false);
    inputRef.current?.blur();
  }, []);

  return (
    <div className="flex flex-col h-full bg-muted/30">
      {/* ── 顶部导航栏 ── */}
      <div className="bg-background border-b border-border">
        <div className="flex items-center h-12 px-4 gap-2">
          <h1 className="flex-1 text-base font-semibold">择校</h1>

          {/* 筛选按钮（带红点指示） */}
          <button
            onClick={() => setFilterOpen(true)}
            className="relative p-2 rounded-lg hover:bg-muted active:bg-muted/80 transition-colors"
            aria-label="筛选"
          >
            <SlidersHorizontal className="size-5" />
            {!allActive && (
              <span className="absolute top-1.5 right-1.5 size-2 rounded-full bg-orange-500" />
            )}
          </button>
        </div>

        {/* 搜索框 */}
        <div className="px-4 pb-3">
          <div
            className={cn(
              "flex items-center gap-2 rounded-xl border px-3 py-2 transition-colors",
              searchActive
                ? "border-orange-400 bg-background"
                : "border-border bg-muted/50"
            )}
          >
            <Search className="size-4 text-muted-foreground shrink-0" />
            <input
              ref={inputRef}
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onFocus={handleSearchFocus}
              onBlur={handleSearchBlur}
              placeholder={
                viewMode === "school"
                  ? "搜索院校名称、城市..."
                  : "搜索专业名称、代码..."
              }
              className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            />
            {search && (
              <button onClick={handleClearSearch} className="p-0.5">
                <X className="size-4 text-muted-foreground" />
              </button>
            )}
          </div>
        </div>

        {/* 分类标签 */}
        <TabNav
          tabs={VIEW_TABS}
          active={viewMode}
          onChange={(v) => setViewMode(v as "school" | "major")}
          activeColor="orange"
        />
      </div>

      {/* ── 内容区 ── */}
      <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
        {viewMode === "school" ? (
          <SchoolListView search={search} />
        ) : (
          <MajorListView search={search} />
        )}
      </div>

      {/* 全局筛选弹窗 */}
      <GlobalFilterDrawer
        open={filterOpen}
        onClose={() => setFilterOpen(false)}
      />
    </div>
  );
}
