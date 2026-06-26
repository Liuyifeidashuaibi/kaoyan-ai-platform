"use client";

import { Suspense, use, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, ChevronDown, RefreshCw } from "lucide-react";
import { EmptyState } from "@/components/schools/empty-state";
import { SkeletonList } from "@/components/schools/skeleton-list";
import { MajorCodeTag } from "@/components/schools/major-code-tag";
import { LevelTags } from "@/components/schools/level-tags";
import {
  getUniversitiesByMajorCode,
  getScoresByMajorCode,
  groupMajorOfferingsByUniversity,
  formatMajorPath,
  type MajorUniversityOffering,
  type ScoreWithMajor,
} from "@/lib/api/schools";
import { SchoolsSyncProvider, useSchoolsSync } from "../../_context/schools-sync-context";
import { cn } from "@/lib/utils";

interface PageProps {
  params: Promise<{ code: string }>;
}

function MajorDetailContent({ code }: { code: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const degreeType = searchParams.get("degree") ?? undefined;
  const { version, refresh, syncing } = useSchoolsSync();

  const [offerings, setOfferings] = useState<MajorUniversityOffering[]>([]);
  const [scores, setScores] = useState<ScoreWithMajor[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const degreeOptions = useMemo(() => {
    const types = [...new Set(offerings.map((o) => o.degree_type).filter(Boolean))] as string[];
    return types.length > 1 ? types : [];
  }, [offerings]);

  const load = () => {
    setLoading(true);
    setLoadError(false);
    Promise.all([
      getUniversitiesByMajorCode(code, degreeType),
      getScoresByMajorCode(code, degreeType),
    ])
      .then(([off, sco]) => {
        setOfferings(off);
        setScores(sco);
      })
      .catch(() => {
        setLoadError(true);
        setOfferings([]);
        setScores([]);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code, degreeType, version]);

  const grouped = useMemo(
    () => groupMajorOfferingsByUniversity(offerings),
    [offerings]
  );

  const scoresByMajorId = useMemo(() => {
    const map = new Map<string, ScoreWithMajor[]>();
    for (const s of scores) {
      const list = map.get(s.major_id) ?? [];
      list.push(s);
      map.set(s.major_id, list);
    }
    for (const [, list] of map) {
      list.sort((a, b) => b.year - a.year);
    }
    return map;
  }, [scores]);

  const first = offerings[0];
  const displayName = first?.name ?? `专业 ${code}`;
  const pathLabel = first
    ? formatMajorPath({
        name: first.name,
        degree_type: first.degree_type ?? degreeType ?? "学硕",
        subject_category: null,
        first_discipline: null,
      })
    : "";

  const directionCount = offerings.length;

  const setDegree = (deg: string | null) => {
    const params = new URLSearchParams(searchParams.toString());
    if (deg) params.set("degree", deg);
    else params.delete("degree");
    router.replace(`?${params.toString()}`, { scroll: false });
  };

  return (
    <div className="min-h-full bg-[#f5f6f8]">
      <div className="mx-auto max-w-4xl px-4 py-6 lg:px-8">
        <div className="mb-4 flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={() => {
              if (window.history.length > 1) router.back();
              else router.push("/schools");
            }}
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
            返回
          </button>
          <button
            type="button"
            onClick={() => {
              void refresh();
              load();
            }}
            disabled={syncing || loading}
            className="inline-flex items-center gap-1 rounded-lg border border-border bg-white px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted/50 disabled:opacity-50"
          >
            <RefreshCw className={cn("size-3.5", (syncing || loading) && "animate-spin")} />
            刷新
          </button>
        </div>

        <div className="mb-6 flex items-start justify-between gap-4 rounded-2xl bg-white p-6 shadow-sm">
          <div>
            <h1 className="text-2xl font-bold">{displayName}</h1>
            {pathLabel && (
              <p className="mt-2 text-sm text-muted-foreground">{pathLabel}</p>
            )}
            <p className="mt-2 text-sm text-muted-foreground">
              {grouped.length} 所院校开设
              {directionCount > grouped.length &&
                ` · ${directionCount} 个招生方向`}
            </p>
            {degreeOptions.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setDegree(null)}
                  className={cn(
                    "rounded-full px-3 py-1 text-xs font-medium",
                    !degreeType
                      ? "bg-[#111827] text-white"
                      : "bg-muted text-muted-foreground hover:bg-muted/80"
                  )}
                >
                  全部
                </button>
                {degreeOptions.map((deg) => (
                  <button
                    key={deg}
                    type="button"
                    onClick={() => setDegree(deg)}
                    className={cn(
                      "rounded-full px-3 py-1 text-xs font-medium",
                      degreeType === deg
                        ? "bg-[#111827] text-white"
                        : "bg-muted text-muted-foreground hover:bg-muted/80"
                    )}
                  >
                    {deg}
                  </button>
                ))}
              </div>
            )}
          </div>
          <MajorCodeTag code={code} />
        </div>

        {loading ? (
          <SkeletonList count={5} />
        ) : loadError ? (
          <EmptyState
            title="加载失败"
            description="请检查网络后重试"
            icon="school"
            action={
              <button
                type="button"
                onClick={() => load()}
                className="rounded-lg border border-border bg-white px-4 py-2 text-sm font-medium text-foreground hover:bg-muted/50"
              >
                重试
              </button>
            }
          />
        ) : grouped.length === 0 ? (
          <EmptyState
            title="暂无开设院校"
            description="该专业代码暂无招生数据，可切换学位类别或稍后刷新"
            icon="school"
          />
        ) : (
          <div className="space-y-3">
            {grouped.map((group) =>
              group.university ? (
                <SchoolOfferingCard
                  key={group.university_id}
                  group={group}
                  majorCode={code}
                  scoresByMajorId={scoresByMajorId}
                />
              ) : null
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function SchoolOfferingCard({
  group,
  majorCode,
  scoresByMajorId,
}: {
  group: ReturnType<typeof groupMajorOfferingsByUniversity>[number];
  majorCode: string;
  scoresByMajorId: Map<string, ScoreWithMajor[]>;
}) {
  const [scoresExpanded, setScoresExpanded] = useState(true);
  const uni = group.university!;
  const collegeLabel =
    group.colleges.filter((c) => c && c !== "未知学院").join("、") ||
    "未标注学院";

  const offeringScores = group.offerings.flatMap(
    (o) => scoresByMajorId.get(o.major_id) ?? []
  );
  const uniqueScores = [...offeringScores].sort((a, b) => b.year - a.year);

  const schoolHref = `/schools/${group.university_id}?tab=scores&major=${majorCode}`;

  return (
    <div className="rounded-2xl bg-white shadow-sm">
      <div className="flex items-start justify-between gap-3 p-4">
        <Link href={schoolHref} className="min-w-0 flex-1 transition-shadow hover:opacity-90">
          <h3 className="text-base font-bold">{uni.name}</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            {uni.province} · {uni.city}
          </p>
          <p className="mt-1 text-xs text-foreground">
            <span className="text-muted-foreground">所属学院：</span>
            {collegeLabel}
          </p>
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
            {group.study_modes.map((m) => (
              <span key={m}>{m}</span>
            ))}
            {group.total_enrollment > 0 && (
              <span>· 合计招 {group.total_enrollment} 人</span>
            )}
            {group.offerings.length > 1 && (
              <span>· {group.offerings.length} 个方向</span>
            )}
          </div>
          <LevelTags university={uni} className="mt-2" />
        </Link>
        <Link
          href={`/schools/${group.university_id}?tab=scores&major=${majorCode}`}
          className="shrink-0 text-xs text-[#111827] hover:underline"
        >
          分数
        </Link>
      </div>

      {uniqueScores.length > 0 && (
        <div className="border-t border-border/60 px-4 pb-4">
          <button
            type="button"
            onClick={() => setScoresExpanded((v) => !v)}
            className="flex w-full items-center justify-between py-3 text-left text-xs font-medium text-muted-foreground"
          >
            <span>分数（{uniqueScores.length} 条，2025/2026）</span>
            <ChevronDown
              className={cn(
                "size-4 transition-transform",
                scoresExpanded && "rotate-180"
              )}
            />
          </button>
          {scoresExpanded && (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[480px] text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-xs text-muted-foreground">
                    <th className="py-2 pl-2 text-left font-medium">年份</th>
                    <th className="py-2 text-center font-medium">总分</th>
                    <th className="py-2 text-center font-medium">政治</th>
                    <th className="py-2 text-center font-medium">外语</th>
                    <th className="py-2 text-center font-medium">业务课一</th>
                    <th className="py-2 text-center font-medium">业务课二</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {uniqueScores.map((s) => (
                    <tr key={s.id} className="hover:bg-muted/20">
                      <td className="py-2 pl-2 font-medium">{s.year}</td>
                      <td className="py-2 text-center text-base font-semibold text-[#111827]">
                        {s.total_score}
                      </td>
                      <td className="py-2 text-center">{s.politics_score}</td>
                      <td className="py-2 text-center">{s.english_score}</td>
                      <td className="py-2 text-center">{s.professional1_score ?? "—"}</td>
                      <td className="py-2 text-center">{s.professional2_score ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function MajorDetailPage({ params }: PageProps) {
  const { code } = use(params);
  return (
    <SchoolsSyncProvider>
      <Suspense fallback={<SkeletonList count={5} />}>
        <MajorDetailContent code={code} />
      </Suspense>
    </SchoolsSyncProvider>
  );
}
