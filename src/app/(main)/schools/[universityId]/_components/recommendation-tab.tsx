"use client";

import { useEffect, useState } from "react";
import { ChevronDown, ExternalLink, Clock } from "lucide-react";
import { BottomFilterSheet } from "@/components/schools/bottom-filter-sheet";
import { EmptyState } from "@/components/schools/empty-state";
import { SkeletonList } from "@/components/schools/skeleton-list";
import { getRecommendations, type Recommendation } from "@/lib/api/schools";
import { cn } from "@/lib/utils";

interface RecommendationTabProps {
  universityId: string;
}

type SheetType = "type" | "status" | null;

const STATUS_STYLE: Record<string, string> = {
  报名中: "bg-green-50 text-green-600 border-green-200",
  未开始: "bg-blue-50 text-blue-600 border-blue-200",
  已结束: "bg-muted text-muted-foreground border-border",
};

const TYPE_STYLE: Record<string, string> = {
  夏令营: "bg-orange-50 text-orange-600 border-orange-200",
  预推免: "bg-purple-50 text-purple-700 border-purple-200",
  正式推免: "bg-teal-50 text-teal-700 border-teal-200",
};

export function RecommendationTab({ universityId }: RecommendationTabProps) {
  const [items, setItems] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [type, setType] = useState("");
  const [status, setStatus] = useState("");
  const [openSheet, setOpenSheet] = useState<SheetType>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const data = await getRecommendations(universityId);
        setItems(data);
      } catch (err) {
        console.error("加载推免信息失败:", err);
        setItems([]);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [universityId]);

  const filtered = items.filter((r) => {
    if (type && r.type !== type) return false;
    if (status && r.status !== status) return false;
    return true;
  });

  return (
    <div className="flex flex-col h-full">
      {/* 筛选栏 */}
      <div className="bg-background border-b border-border px-4 py-2.5 flex items-center gap-2">
        <span className="text-xs text-muted-foreground flex-1">推免通知</span>
        <FilterChip
          label={type || "推免类型"}
          active={!!type}
          onClick={() => setOpenSheet("type")}
        />
        <FilterChip
          label={status || "状态"}
          active={!!status}
          onClick={() => setOpenSheet("status")}
        />
      </div>

      {/* 内容 */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <SkeletonList count={4} className="rounded-none" />
        ) : filtered.length === 0 ? (
          <EmptyState
            title="暂无推免信息"
            description="该院校暂无收录推免记录"
          />
        ) : (
          <div className="pb-8 bg-card">
            {filtered.map((item) => (
              <RecommendationRow key={item.id} item={item} />
            ))}
          </div>
        )}
      </div>

      <BottomFilterSheet
        open={openSheet === "type"}
        onClose={() => setOpenSheet(null)}
        title="推免类型"
        options={[
          { value: "夏令营", label: "夏令营" },
          { value: "预推免", label: "预推免" },
          { value: "正式推免", label: "正式推免" },
        ]}
        selected={type}
        onSelect={setType}
      />
      <BottomFilterSheet
        open={openSheet === "status"}
        onClose={() => setOpenSheet(null)}
        title="状态"
        options={[
          { value: "未开始", label: "未开始" },
          { value: "报名中", label: "报名中" },
          { value: "已结束", label: "已结束" },
        ]}
        selected={status}
        onSelect={setStatus}
      />
    </div>
  );
}

function RecommendationRow({ item }: { item: Recommendation }) {
  return (
    <div className="px-4 py-3.5 border-b border-border/60 last:border-0">
      <div className="flex items-start justify-between gap-2 mb-2">
        <p className="text-sm font-medium flex-1 leading-snug line-clamp-2">
          {item.title}
        </p>
        <div className="flex flex-col gap-1 shrink-0 items-end">
          <span
            className={cn(
              "inline-flex items-center rounded px-1.5 py-px text-[10px] font-medium border",
              TYPE_STYLE[item.type] ?? "bg-muted text-muted-foreground border-border"
            )}
          >
            {item.type}
          </span>
          <span
            className={cn(
              "inline-flex items-center rounded px-1.5 py-px text-[10px] font-medium border",
              STATUS_STYLE[item.status] ??
                "bg-muted text-muted-foreground border-border"
            )}
          >
            {item.status}
          </span>
        </div>
      </div>

      {(item.start_time || item.end_time) && (
        <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1.5">
          <Clock className="size-3" />
          {item.start_time && <span>{item.start_time}</span>}
          {item.start_time && item.end_time && <span>~</span>}
          {item.end_time && <span>{item.end_time}</span>}
        </div>
      )}

      {item.url && (
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs text-orange-500 underline underline-offset-2"
        >
          查看原文 <ExternalLink className="size-3" />
        </a>
      )}
    </div>
  );
}

function FilterChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex shrink-0 items-center gap-0.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors",
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
