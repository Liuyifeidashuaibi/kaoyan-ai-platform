"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, RefreshCw, ExternalLink } from "lucide-react";
import { TabNav } from "@/components/schools/tab-nav";
import { SkeletonDetail } from "@/components/schools/skeleton-list";
import { EmptyState } from "@/components/schools/empty-state";
import { LevelTags } from "@/components/schools/level-tags";
import {
  getUniversity,
  getMajors,
  getScoredMajorCodes,
  getUniversityInitial,
  getExamZone,
  type University,
  type Major,
} from "@/lib/api/schools";
import { useSchoolsSync } from "../../_context/schools-sync-context";
import { OverviewTab } from "./overview-tab";
import { MajorsTab } from "./majors-tab";
import { ScoresTab } from "./scores-tab";

const DETAIL_TABS = [
  { value: "overview", label: "院校概况" },
  { value: "majors", label: "专业" },
  { value: "scores", label: "分数" },
] as const;

type DetailTab = (typeof DETAIL_TABS)[number]["value"];

function isDetailTab(v: string | null): v is DetailTab {
  return v === "overview" || v === "majors" || v === "scores";
}

function resolveInitialTab(tabParam: string | null, majorParam: string | null): DetailTab {
  if (isDetailTab(tabParam)) return tabParam;
  if (majorParam) return "majors";
  return "overview";
}

interface UniversityDetailClientProps {
  universityId: string;
}

function UniversityDetailContent({ universityId }: UniversityDetailClientProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tabParam = searchParams.get("tab");
  const majorParam = searchParams.get("major");

  const [university, setUniversity] = useState<University | null>(null);
  const [majors, setMajors] = useState<Major[]>([]);
  const [scoredMajorCodes, setScoredMajorCodes] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [majorsLoading, setMajorsLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const majorsLoadedRef = useRef(false);
  const scoredLoadedRef = useRef(false);
  const [activeTab, setActiveTab] = useState<DetailTab>(() =>
    resolveInitialTab(tabParam, majorParam)
  );
  const { version, refresh: syncRefresh, syncing } = useSchoolsSync();
  const [refreshKey, setRefreshKey] = useState(0);

  const updateUrl = useCallback(
    (tab: DetailTab, major?: string | null) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("tab", tab);
      if (major) {
        params.set("major", major);
      } else {
        params.delete("major");
      }
      router.replace(`?${params.toString()}`, { scroll: false });
    },
    [router, searchParams]
  );

  const handleTabChange = useCallback(
    (tab: string) => {
      if (!isDetailTab(tab)) return;
      setActiveTab(tab);
      if (majorParam) {
        updateUrl(tab, majorParam);
      } else {
        updateUrl(tab);
      }
    },
    [majorParam, updateUrl]
  );

  const handleViewScores = useCallback(
    (majorCode: string) => {
      setActiveTab("scores");
      updateUrl("scores", majorCode);
    },
    [updateUrl]
  );

  const handleViewMajors = useCallback(
    (majorCode: string) => {
      setActiveTab("majors");
      updateUrl("majors", majorCode);
    },
    [updateUrl]
  );

  const handleSelectMajor = useCallback(
    (majorCode: string) => {
      if (activeTab === "majors") {
        updateUrl("majors", majorCode);
      }
    },
    [activeTab, updateUrl]
  );

  const handleClearMajorHighlight = useCallback(() => {
    updateUrl(activeTab);
  }, [activeTab, updateUrl]);

  useEffect(() => {
    if (isDetailTab(tabParam)) setActiveTab(tabParam);
  }, [tabParam]);

  const loadUniversity = async () => {
    setLoading(true);
    setLoadError(null);
    majorsLoadedRef.current = false;
    scoredLoadedRef.current = false;
    setMajors([]);
    setScoredMajorCodes(new Set());
    try {
      const uni = await getUniversity(universityId);
      setUniversity(uni);
      if (!uni) setLoadError("not_found");
    } catch (err) {
      console.error("加载院校详情失败:", err);
      setLoadError("failed");
      setUniversity(null);
    } finally {
      setLoading(false);
    }
  };

  const ensureMajors = useCallback(async () => {
    if (!university || majorsLoadedRef.current) return;
    setMajorsLoading(true);
    try {
      const ms = await getMajors(universityId);
      setMajors(ms);
      majorsLoadedRef.current = true;
    } catch (err) {
      console.error("加载专业列表失败:", err);
    } finally {
      setMajorsLoading(false);
    }
  }, [university, universityId]);

  const ensureScoredCodes = useCallback(async () => {
    if (!university || scoredLoadedRef.current) return;
    try {
      const scored = await getScoredMajorCodes(universityId);
      setScoredMajorCodes(scored);
      scoredLoadedRef.current = true;
    } catch (err) {
      console.error("加载分数专业代码失败:", err);
    }
  }, [university, universityId]);

  useEffect(() => {
    void loadUniversity();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [universityId, refreshKey, version]);

  useEffect(() => {
    if (!university) return;
    if (activeTab === "overview" || activeTab === "majors") {
      void ensureMajors();
    }
    if (activeTab === "majors") {
      void ensureScoredCodes();
    }
  }, [activeTab, ensureMajors, ensureScoredCodes, university]);

  if (loading) {
    return (
      <div className="min-h-full bg-[#f5f6f8]">
        <SkeletonDetail />
      </div>
    );
  }

  if (!university) {
    return (
      <div className="min-h-full bg-[#f5f6f8] p-6">
        <EmptyState
          title={loadError === "failed" ? "加载失败" : "院校不存在"}
          description={
            loadError === "failed"
              ? "网络或数据库异常，请稍后重试"
              : "请返回重新选择"
          }
          icon="school"
          action={
            loadError === "failed" ? (
              <button
                type="button"
                onClick={() => loadUniversity()}
                className="rounded-lg border border-border bg-white px-4 py-2 text-sm font-medium text-foreground hover:bg-muted/50"
              >
                重试
              </button>
            ) : undefined
          }
        />
      </div>
    );
  }

  const initial = getUniversityInitial(university.name);
  const zone = getExamZone(university.province);
  const gradUrl = university.graduate_url;
  const websiteUrl = university.website;

  return (
    <div className="relative min-h-full bg-[#f5f6f8] pb-8">
      <div className="mx-auto max-w-5xl">
        <div className="flex items-center gap-2 px-4 py-3 lg:px-0">
          <button
            type="button"
            onClick={() => router.back()}
            className="rounded-lg p-2 hover:bg-white/80"
            aria-label="返回"
          >
            <ArrowLeft className="size-5" />
          </button>
          <h1 className="flex-1 truncate text-sm font-semibold lg:text-base">
            {university.name}
          </h1>
          <button
            type="button"
            onClick={() => {
              void syncRefresh();
              setRefreshKey((k) => k + 1);
            }}
            disabled={syncing}
            className="rounded-lg p-2 hover:bg-white/80 disabled:opacity-50"
            aria-label="刷新"
          >
            <RefreshCw className={`size-5 ${syncing ? "animate-spin" : ""}`} />
          </button>
        </div>

        <div className="relative mx-4 overflow-hidden rounded-2xl border border-border bg-white lg:mx-0">
          <div className="relative flex items-end gap-4 px-6 py-8">
            {university.logo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={university.logo_url}
                alt={university.name}
                className="size-20 rounded-full border-4 border-border object-cover shadow-lg"
              />
            ) : (
              <div className="flex size-20 items-center justify-center rounded-full border-4 border-border bg-black/5 shadow-lg">
                <span className="text-2xl font-bold text-[#111827]">{initial}</span>
              </div>
            )}
            <div className="min-w-0 flex-1 pb-1 text-[#111827]">
              <h2 className="text-xl font-bold lg:text-2xl">{university.name}</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                {university.province} · {university.city} · {zone}
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <LevelTags university={university} />
              </div>
            </div>
          </div>
        </div>

        <div className="mx-4 mt-4 flex gap-2 lg:mx-0">
          <a
            href={websiteUrl ?? "#"}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => !websiteUrl && e.preventDefault()}
            aria-disabled={!websiteUrl}
            className={`flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-border bg-white py-3 text-sm font-medium text-foreground hover:bg-muted/50 ${!websiteUrl ? "pointer-events-none opacity-40" : ""}`}
          >
            访问官网
            <ExternalLink className="size-3.5 text-muted-foreground" />
          </a>
          <a
            href={gradUrl ?? "#"}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => !gradUrl && e.preventDefault()}
            aria-disabled={!gradUrl}
            className={`flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-border bg-white py-3 text-sm font-medium text-foreground hover:bg-muted/50 ${!gradUrl ? "pointer-events-none opacity-40" : ""}`}
          >
            访问研究生官网
            <ExternalLink className="size-3.5" />
          </a>
        </div>

        <div className="mx-4 mt-4 overflow-hidden rounded-t-2xl bg-white shadow-sm lg:mx-0">
          <TabNav
            tabs={[...DETAIL_TABS]}
            active={activeTab}
            onChange={handleTabChange}
            activeColor="brand"
            className="border-none"
          />
        </div>

        <div className="mx-4 min-h-[400px] rounded-b-2xl bg-white shadow-sm lg:mx-0">
          {activeTab === "overview" && (
            majorsLoading && majors.length === 0 ? (
              <div className="p-6">
                <SkeletonDetail />
              </div>
            ) : (
              <OverviewTab
                university={university}
                majors={majors}
                universityId={universityId}
                dataVersion={version}
                highlightMajorCode={majorParam ?? undefined}
                onGoMajors={() => handleTabChange("majors")}
                onGoScores={() => handleTabChange("scores")}
                onClearMajorHighlight={
                  majorParam ? handleClearMajorHighlight : undefined
                }
              />
            )
          )}
          {activeTab === "majors" && (
            majorsLoading && majors.length === 0 ? (
              <div className="p-6">
                <SkeletonDetail />
              </div>
            ) : (
              <MajorsTab
                majors={majors}
                scoredMajorCodes={scoredMajorCodes}
                highlightMajorCode={majorParam ?? undefined}
                onViewScores={handleViewScores}
                onSelectMajor={handleSelectMajor}
                onClearHighlight={majorParam ? handleClearMajorHighlight : undefined}
              />
            )
          )}
          {activeTab === "scores" && (
            <ScoresTab
              universityId={universityId}
              dataVersion={version}
              highlightMajorCode={majorParam ?? undefined}
              onClearHighlight={majorParam ? handleClearMajorHighlight : undefined}
            />
          )}
        </div>
      </div>
    </div>
  );
}

export function UniversityDetailClient(props: UniversityDetailClientProps) {
  return (
    <Suspense
      fallback={
        <div className="min-h-full bg-[#f5f6f8]">
          <SkeletonDetail />
        </div>
      }
    >
      <UniversityDetailContent {...props} />
    </Suspense>
  );
}
