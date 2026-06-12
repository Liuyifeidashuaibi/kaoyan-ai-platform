"use client";

import { useEffect, useState } from "react";
import { ChevronDown, Search, X } from "lucide-react";
import { BottomFilterSheet } from "@/components/schools/bottom-filter-sheet";
import { EmptyState } from "@/components/schools/empty-state";
import { SkeletonList } from "@/components/schools/skeleton-list";
import { getScores, getScoreYears, getLineDiffColor, type ScoreWithMajor } from "@/lib/api/schools";
import { cn } from "@/lib/utils";

interface ScoresTabProps {
  universityId: string;
}

export function ScoresTab({ universityId }: ScoresTabProps) {
  const [scores, setScores] = useState<ScoreWithMajor[]>([]);
  const [years, setYears] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);

  // 筛选状态
  const [year, setYear] = useState("");
  const [degreeType, setDegreeType] = useState("");
  const [search, setSearch] = useState("");
  const [openSheet, setOpenSheet] = useState<"year" | "degree" | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const [s, ys] = await Promise.all([
          getScores(universityId),
          getScoreYears(universityId),
        ]);
        setScores(s);
        setYears(ys);
        if (ys.length > 0) setYear(String(ys[0]));
      } catch (err) {
        console.error("加载分数线失败:", err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [universityId]);

  const filtered = scores.filter((s) => {
    if (year && String(s.year) !== year) return false;
    if (degreeType && s.majors?.degree_type !== degreeType) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      return (
        (s.majors?.name ?? "").toLowerCase().includes(q) ||
        (s.majors?.code ?? "").toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="flex flex-col h-full">
      {/* 筛选栏 */}
      <div className="bg-background border-b border-border px-4 py-2.5 flex items-center gap-2">
        <FilterChip
          label={year ? `${year}年` : "年份"}
          active={!!year}
          onClick={() => setOpenSheet("year")}
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
            className="w-16 bg-transparent text-xs outline-none placeholder:text-muted-foreground"
          />
          {search && (
            <button onClick={() => setSearch("")}>
              <X className="size-3 text-muted-foreground" />
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-x-auto overflow-y-auto">
        {loading ? (
          <SkeletonList count={6} className="rounded-none" />
        ) : filtered.length === 0 ? (
          <EmptyState
            title="暂无分数线数据"
            description="数据将在每年3-4月国家线公布后更新"
          />
        ) : (
          <table className="w-full min-w-[520px] text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50 text-xs text-muted-foreground">
                <th className="py-2.5 pl-4 text-left font-medium">年份</th>
                <th className="py-2.5 text-left font-medium">专业</th>
                <th className="py-2.5 text-center font-medium">总分</th>
                <th className="py-2.5 text-center font-medium">政治</th>
                <th className="py-2.5 text-center font-medium">英语</th>
                <th className="py-2.5 text-center font-medium">专业①</th>
                <th className="py-2.5 pr-4 text-center font-medium">国家线差</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60 bg-card">
              {filtered.map((s) => (
                <ScoreRow key={s.id} score={s} />
              ))}
            </tbody>
          </table>
        )}
      </div>

      <BottomFilterSheet
        open={openSheet === "year"}
        onClose={() => setOpenSheet(null)}
        title="选择年份"
        options={years.map((y) => ({ value: String(y), label: `${y}年` }))}
        selected={year}
        onSelect={setYear}
        allLabel="全部年份"
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

function ScoreRow({ score }: { score: ScoreWithMajor }) {
  return (
    <tr className="hover:bg-muted/30">
      <td className="py-3 pl-4 text-sm font-medium">{score.year}</td>
      <td className="py-3 pr-2">
        <p className="text-sm">{score.majors?.name ?? "—"}</p>
        <p className="text-xs text-muted-foreground">
          {score.majors?.code} · {score.majors?.degree_type}
        </p>
      </td>
      <td className="py-3 text-center font-semibold">{score.total_score}</td>
      <td className="py-3 text-center">{score.politics_score}</td>
      <td className="py-3 text-center">{score.english_score}</td>
      <td className="py-3 text-center">{score.professional1_score ?? "—"}</td>
      <td className="py-3 pr-4 text-center">
        {score.line_diff != null ? (
          <span
            className={cn(
              "rounded px-1.5 py-0.5 text-xs font-semibold",
              score.line_diff > 0
                ? "bg-green-50 text-green-700"
                : score.line_diff < 0
                  ? "bg-red-50 text-red-600"
                  : "bg-muted text-muted-foreground"
            )}
          >
            {score.line_diff > 0 ? "+" : ""}
            {score.line_diff}
          </span>
        ) : (
          <span className={getLineDiffColor(null)}>—</span>
        )}
      </td>
    </tr>
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
