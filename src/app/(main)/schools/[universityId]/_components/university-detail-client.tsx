"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, RefreshCw } from "lucide-react";
import { TabNav } from "@/components/schools/tab-nav";
import { SkeletonDetail } from "@/components/schools/skeleton-list";
import { EmptyState } from "@/components/schools/empty-state";
import {
  getUniversity,
  getMajors,
  getUniversityLevelTags,
  getUniversityInitial,
  type University,
  type Major,
} from "@/lib/api/schools";
import { OverviewTab } from "./overview-tab";
import { MajorsTab } from "./majors-tab";
import { ScoresTab } from "./scores-tab";
import { AnnouncementsTab } from "./announcements-tab";
import { AdjustmentTab } from "./adjustment-tab";
import { RecommendationTab } from "./recommendation-tab";
import { cn } from "@/lib/utils";

const DETAIL_TABS = [
  { value: "overview", label: "概况" },
  { value: "majors", label: "专业" },
  { value: "scores", label: "分数" },
  { value: "announcements", label: "公告" },
  { value: "adjustment", label: "调剂" },
  { value: "recommendation", label: "推免" },
];

const LEVEL_TAG_STYLE: Record<string, string> = {
  "985": "bg-orange-100 text-orange-700 border-orange-200",
  "211": "bg-blue-100 text-blue-700 border-blue-200",
  双一流A: "bg-purple-100 text-purple-700 border-purple-200",
  双一流B: "bg-violet-100 text-violet-700 border-violet-200",
  一流学科: "bg-teal-100 text-teal-700 border-teal-200",
};

interface UniversityDetailClientProps {
  universityId: string;
}

export function UniversityDetailClient({
  universityId,
}: UniversityDetailClientProps) {
  const router = useRouter();
  const [university, setUniversity] = useState<University | null>(null);
  const [majors, setMajors] = useState<Major[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("overview");
  const [refreshKey, setRefreshKey] = useState(0);

  const load = async () => {
    setLoading(true);
    try {
      const [uni, ms] = await Promise.all([
        getUniversity(universityId),
        getMajors(universityId),
      ]);
      setUniversity(uni);
      setMajors(ms);
    } catch (err) {
      console.error("加载院校详情失败:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [universityId, refreshKey]);

  if (loading) {
    return (
      <div className="flex flex-col h-full bg-background">
        <TopBar title="加载中..." onBack={() => router.back()} />
        <SkeletonDetail />
      </div>
    );
  }

  if (!university) {
    return (
      <div className="flex flex-col h-full bg-background">
        <TopBar title="院校详情" onBack={() => router.back()} />
        <EmptyState title="院校不存在" description="请返回重新选择" icon="school" />
      </div>
    );
  }

  const tags = getUniversityLevelTags(university);
  const initial = getUniversityInitial(university.name);

  return (
    <div className="flex flex-col h-full bg-muted/30">
      {/* ── 顶部导航 ── */}
      <TopBar
        title={university.name}
        onBack={() => router.back()}
        onRefresh={() => setRefreshKey((k) => k + 1)}
      />

      {/* ── 院校头部信息卡 ── */}
      <div className="bg-background px-4 pt-4 pb-3 border-b border-border">
        <div className="flex items-center gap-4">
          {university.logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={university.logo_url}
              alt={university.name}
              className="size-20 rounded-full object-cover border-2 border-border shadow-sm"
            />
          ) : (
            <div className="size-20 rounded-full bg-orange-50 border-2 border-orange-100 flex items-center justify-center shadow-sm">
              <span className="text-xl font-bold text-orange-600">
                {initial}
              </span>
            </div>
          )}
          <div className="flex-1 min-w-0">
            <h2 className="text-base font-bold mb-2">{university.name}</h2>
            <div className="flex flex-wrap gap-1.5">
              {tags.map((tag) => (
                <span
                  key={tag}
                  className={cn(
                    "inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold border",
                    LEVEL_TAG_STYLE[tag] ??
                      "bg-muted text-muted-foreground border-border"
                  )}
                >
                  {tag}
                </span>
              ))}
              <span className="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium border bg-muted text-muted-foreground border-border">
                {university.province}·{university.city}
              </span>
              <span className="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium border bg-muted text-muted-foreground border-border">
                {university.school_type}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ── 标签导航（固定） ── */}
      <div className="bg-background border-b border-border shrink-0">
        <TabNav
          tabs={DETAIL_TABS}
          active={activeTab}
          onChange={setActiveTab}
          activeColor="orange"
        />
      </div>

      {/* ── 内容区 ── */}
      <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
        {activeTab === "overview" && (
          <div className="flex-1 overflow-y-auto">
            <OverviewTab university={university} majors={majors} />
          </div>
        )}
        {activeTab === "majors" && <MajorsTab majors={majors} />}
        {activeTab === "scores" && <ScoresTab universityId={universityId} />}
        {activeTab === "announcements" && (
          <AnnouncementsTab universityId={universityId} />
        )}
        {activeTab === "adjustment" && (
          <AdjustmentTab universityId={universityId} />
        )}
        {activeTab === "recommendation" && (
          <RecommendationTab universityId={universityId} />
        )}
      </div>
    </div>
  );
}

function TopBar({
  title,
  onBack,
  onRefresh,
}: {
  title: string;
  onBack: () => void;
  onRefresh?: () => void;
}) {
  return (
    <div className="flex items-center h-12 px-2 gap-1 bg-background border-b border-border shrink-0">
      <button
        onClick={onBack}
        className="p-2 rounded-lg hover:bg-muted active:bg-muted/80 transition-colors"
        aria-label="返回"
      >
        <ArrowLeft className="size-5" />
      </button>
      <h1 className="flex-1 text-sm font-semibold text-center truncate px-2">
        {title}
      </h1>
      {onRefresh ? (
        <button
          onClick={onRefresh}
          className="p-2 rounded-lg hover:bg-muted active:bg-muted/80 transition-colors"
          aria-label="刷新"
        >
          <RefreshCw className="size-5" />
        </button>
      ) : (
        <div className="size-9" />
      )}
    </div>
  );
}
