"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { TabNav } from "@/components/schools/tab-nav";
import { LoadingProgressBar, SkeletonList } from "@/components/schools/skeleton-list";
import { SchoolListView } from "./school-list-view";
import { MajorListView } from "./major-list-view";
import { SearchResultsView } from "./search-results-view";
import { SchoolSearchOverlay } from "./school-search-overlay";
import { isSupabaseConfigured } from "@/lib/supabase/client";
import { EmptyState } from "@/components/schools/empty-state";
import { useSchoolsSync } from "../_context/schools-sync-context";
import { cn } from "@/lib/utils";

const VIEW_TABS = [
  { value: "school", label: "按院校检索" },
  { value: "major", label: "按专业检索" },
];

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(t);
  }, [value, delayMs]);
  return debounced;
}

function SchoolsPageContent({ basePath = "/schools" }: { basePath?: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const viewParam = searchParams.get("view");
  const qParam = searchParams.get("q") ?? "";
  const viewMode: "school" | "major" = viewParam === "major" ? "major" : "school";

  const [search, setSearch] = useState(qParam);
  const [majorListSearch, setMajorListSearch] = useState("");
  const [searchOpen, setSearchOpen] = useState(!!qParam);
  const [majorTabVisited, setMajorTabVisited] = useState(viewMode === "major");
  const [schoolLoading, setSchoolLoading] = useState(true);
  const [majorLoading, setMajorLoading] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const { syncing } = useSchoolsSync();
  const debouncedSearch = useDebouncedValue(search.trim(), 300);
  const isSearching = debouncedSearch.length > 0;
  const showMajorList = viewMode === "major" || majorTabVisited;

  const updateUrl = useCallback(
    (view: "school" | "major", q: string) => {
      const params = new URLSearchParams();
      if (view === "major") params.set("view", "major");
      if (q) params.set("q", q);
      const qs = params.toString();
      router.replace(qs ? `${basePath}?${qs}` : basePath, { scroll: false });
    },
    [router, basePath]
  );

  useEffect(() => {
    setSearch(qParam);
    setSearchOpen(!!qParam);
  }, [qParam]);

  const handleViewChange = useCallback(
    (v: string) => {
      const next = v as "school" | "major";
      if (isSearching) {
        setSearch("");
        setSearchOpen(false);
        updateUrl(next, "");
      } else {
        updateUrl(next, "");
      }
      if (next === "major") setMajorTabVisited(true);
    },
    [isSearching, updateUrl]
  );

  const handleSearchChange = useCallback(
    (value: string) => {
      setSearch(value);
      if (!value.trim()) {
        updateUrl(viewMode, "");
      }
    },
    [updateUrl, viewMode]
  );

  const handleCloseSearch = useCallback(() => {
    setSearch("");
    setSearchOpen(false);
    updateUrl(viewMode, "");
  }, [updateUrl, viewMode]);

  const handleBrowseAllMajors = useCallback(
    (keyword: string) => {
      setMajorListSearch(keyword);
      setSearch("");
      setSearchOpen(false);
      setMajorTabVisited(true);
      updateUrl("major", "");
    },
    [updateUrl]
  );

  useEffect(() => {
    if (debouncedSearch) updateUrl(viewMode, debouncedSearch);
  }, [debouncedSearch, updateUrl, viewMode]);

  const showProgress =
    syncing ||
    searchLoading ||
    (viewMode === "school" && !isSearching && schoolLoading) ||
    (viewMode === "major" && !isSearching && majorLoading);

  return (
    <div className="min-h-full bg-white text-[#111827]">
      <LoadingProgressBar active={showProgress} />
      <SchoolSearchOverlay
        open={searchOpen}
        value={search}
        onChange={handleSearchChange}
        onClose={handleCloseSearch}
      />

      <div className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
        <div className="mb-4 rounded-2xl bg-white shadow-sm ring-1 ring-black/5">
          <TabNav
            tabs={VIEW_TABS}
            active={viewMode}
            onChange={handleViewChange}
            activeColor="brand"
            className={cn("border-none rounded-t-2xl", isSearching && "opacity-60")}
          />
          {isSearching && (
            <p className="border-t border-border/60 px-4 py-2 text-xs text-muted-foreground">
              正在全库搜索「{debouncedSearch}」· 切换板块将退出搜索
            </p>
          )}
        </div>

        {isSearching ? (
          <SearchResultsView
            keyword={debouncedSearch}
            onLoadingChange={setSearchLoading}
            onBrowseAllMajors={handleBrowseAllMajors}
          />
        ) : (
          <>
            <div className={viewMode === "school" ? undefined : "hidden"}>
              <SchoolListView search="" onLoadingChange={setSchoolLoading} />
            </div>
            {showMajorList && (
              <div className={viewMode === "major" ? undefined : "hidden"}>
                <MajorListView
                  search={majorListSearch}
                  onLoadingChange={setMajorLoading}
                  onClearInjectedSearch={() => setMajorListSearch("")}
                />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export function SchoolsPageClient({ basePath = "/schools" }: { basePath?: string } = {}) {
  if (!isSupabaseConfigured()) {
    return (
      <div className="min-h-full bg-white px-4 py-12">
        <EmptyState
          title="数据库未配置"
          description="请在 .env.local 中设置 NEXT_PUBLIC_SUPABASE_URL 和 NEXT_PUBLIC_SUPABASE_ANON_KEY"
          icon="school"
        />
      </div>
    );
  }

  return (
    <Suspense
      fallback={
        <div className="min-h-full bg-[#f5f6f8]">
          <LoadingProgressBar active />
          <div className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
            <SkeletonList count={4} />
          </div>
        </div>
      }
    >
      <SchoolsPageContent basePath={basePath} />
    </Suspense>
  );
}
