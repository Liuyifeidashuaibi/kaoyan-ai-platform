"use client";

import { useEffect, useState } from "react";
import { ChevronDown } from "lucide-react";
import { BottomFilterSheet } from "@/components/schools/bottom-filter-sheet";
import { EmptyState } from "@/components/schools/empty-state";
import { SkeletonList } from "@/components/schools/skeleton-list";
import { getAdjustments, type Adjustment } from "@/lib/api/schools";

interface AdjustmentTabProps {
  universityId: string;
}

export function AdjustmentTab({ universityId }: AdjustmentTabProps) {
  const [adjustments, setAdjustments] = useState<Adjustment[]>([]);
  const [years, setYears] = useState<number[]>([]);
  const [year, setYear] = useState("");
  const [loading, setLoading] = useState(true);
  const [sheetOpen, setSheetOpen] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const data = await getAdjustments(universityId);
        setAdjustments(data);
        const uniqueYears = [...new Set(data.map((d) => d.year))].sort(
          (a, b) => b - a
        );
        setYears(uniqueYears);
        if (uniqueYears.length > 0) setYear(String(uniqueYears[0]));
      } catch (err) {
        console.error("加载调剂信息失败:", err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [universityId]);

  const filtered = adjustments.filter(
    (a) => !year || String(a.year) === year
  );

  return (
    <div className="flex flex-col h-full">
      {/* 筛选栏 */}
      <div className="bg-background border-b border-border px-4 py-2.5 flex items-center gap-2">
        <span className="text-xs text-muted-foreground flex-1">历年调剂信息</span>
        <button
          onClick={() => setSheetOpen(true)}
          className="flex items-center gap-0.5 rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs font-medium text-muted-foreground"
        >
          {year ? `${year}年` : "年份"}
          <ChevronDown className="size-3" />
        </button>
      </div>

      {/* 内容 */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <SkeletonList count={4} className="rounded-none" />
        ) : filtered.length === 0 ? (
          <EmptyState
            title="暂无调剂信息"
            description="该院校暂无收录调剂记录"
          />
        ) : (
          <div className="pb-8 bg-card">
            {filtered.map((adj) => (
              <AdjustmentRow key={adj.id} adj={adj} />
            ))}
          </div>
        )}
      </div>

      <BottomFilterSheet
        open={sheetOpen}
        onClose={() => setSheetOpen(false)}
        title="选择年份"
        options={years.map((y) => ({ value: String(y), label: `${y}年` }))}
        selected={year}
        onSelect={setYear}
        allLabel="全部年份"
      />
    </div>
  );
}

function AdjustmentRow({ adj }: { adj: Adjustment }) {
  return (
    <div className="px-4 py-3.5 border-b border-border/60 last:border-0">
      <div className="flex items-start justify-between gap-2 mb-2">
        <p className="text-sm font-medium flex-1">{adj.major_name}</p>
        <span className="shrink-0 rounded bg-orange-50 border border-orange-100 px-2 py-0.5 text-xs text-orange-600 font-medium">
          {adj.year}年
        </span>
      </div>
      <div className="space-y-1 text-xs text-muted-foreground">
        {adj.quota != null && (
          <p>
            调剂名额：
            <span className="text-foreground font-medium">{adj.quota} 人</span>
          </p>
        )}
        {adj.requirements && (
          <p className="leading-relaxed">要求：{adj.requirements}</p>
        )}
        {adj.contact && <p>联系方式：{adj.contact}</p>}
        {adj.url && (
          <a
            href={adj.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-orange-500 underline underline-offset-2 inline-block mt-1"
          >
            查看原文
          </a>
        )}
      </div>
    </div>
  );
}
