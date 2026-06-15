"use client";

import { useEffect, useState } from "react";
import { ChevronDown, ChevronUp, MapPin } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  getScores,
  getScoreYears,
  getUniversityLevelTags,
  isValidMajorRecord,
  computeCollegeStats,
  type University,
  type Major,
} from "@/lib/api/schools";

interface OverviewTabProps {
  university: University;
  majors: Major[];
  universityId: string;
  dataVersion?: number;
  highlightMajorCode?: string;
  onGoMajors?: () => void;
  onGoScores?: () => void;
  onClearMajorHighlight?: () => void;
}

export function OverviewTab({
  university,
  majors,
  universityId,
  dataVersion = 0,
  highlightMajorCode,
  onGoMajors,
  onGoScores,
  onClearMajorHighlight,
}: OverviewTabProps) {
  const [introExpanded, setIntroExpanded] = useState(false);
  const [scoreCount, setScoreCount] = useState(0);
  const [scoreYears, setScoreYears] = useState<number[]>([]);

  const intro = university.intro ?? "";
  const tags = getUniversityLevelTags(university);

  const validMajors = majors.filter((m) => isValidMajorRecord(m));
  const degreeTypes = [...new Set(validMajors.map((m) => m.degree_type).filter(Boolean))] as string[];
  const studyModes = [...new Set(validMajors.map((m) => m.study_mode).filter(Boolean))] as string[];
  const totalEnrollment = validMajors.reduce((s, m) => s + (m.enrollment_count ?? 0), 0);
  const collegeStats = computeCollegeStats(validMajors);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getScores(universityId), getScoreYears(universityId)])
      .then(([scores, years]) => {
        if (!cancelled) {
          setScoreCount(scores.length);
          setScoreYears(years);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setScoreCount(0);
          setScoreYears([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [universityId, dataVersion]);

  const latestYear = scoreYears[0];

  const highlightDigits = highlightMajorCode?.replace(/\D/g, "").slice(0, 6);
  const highlightedMajor = highlightDigits
    ? validMajors.find(
        (m) => m.code?.replace(/\D/g, "").slice(0, 6) === highlightDigits
      )
    : undefined;

  return (
    <div className="space-y-3 p-4">
      {highlightDigits && (onGoMajors || onGoScores) && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[#007AFF]/15 bg-[#007AFF]/10 px-4 py-2.5 text-xs">
          <span className="text-[#007AFF]">
            已关联专业
            {highlightedMajor ? `：${highlightedMajor.name}` : ` ${highlightDigits}`}
          </span>
          <div className="flex flex-wrap gap-2">
            {onGoMajors && (
              <button
                type="button"
                onClick={onGoMajors}
                className="font-medium text-[#007AFF] hover:underline"
              >
                查看专业
              </button>
            )}
            {onGoScores && (
              <button
                type="button"
                onClick={onGoScores}
                className="font-medium text-[#007AFF] hover:underline"
              >
                查看分数
              </button>
            )}
            {onClearMajorHighlight && (
              <button
                type="button"
                onClick={onClearMajorHighlight}
                className="text-muted-foreground hover:underline"
              >
                取消
              </button>
            )}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {[
          { label: "招生专业", value: validMajors.length, unit: "个", onClick: onGoMajors },
          {
            label: "已标注学院",
            value: collegeStats.labeledColleges || "—",
            unit: collegeStats.labeledColleges ? "个" : "",
            onClick: onGoMajors,
          },
          {
            label: "分数",
            value: scoreCount || "—",
            unit: scoreCount ? "条" : "",
            onClick: onGoScores,
          },
          {
            label: "拟招生",
            value: totalEnrollment || "—",
            unit: totalEnrollment ? "人" : "",
            onClick: undefined,
          },
        ].map((item) => (
          <button
            key={item.label}
            type="button"
            onClick={item.onClick}
            disabled={!item.onClick}
            className={cn(
              "flex flex-col items-center rounded-xl border border-border bg-card py-3",
              item.onClick && "cursor-pointer hover:border-[#007AFF]/20 hover:bg-[#007AFF]/10"
            )}
          >
            <p className="text-xl font-bold text-[#007AFF] leading-none">
              {item.value}
              <span className="text-xs font-normal text-muted-foreground">{item.unit}</span>
            </p>
            <p className="mt-1 text-xs text-muted-foreground">{item.label}</p>
          </button>
        ))}
      </div>

      {latestYear && scoreCount > 0 && (
        <p className="text-xs text-muted-foreground px-1">
          已收录 {scoreYears.join("、")} 年分数，最新为 {latestYear} 年
        </p>
      )}

      {collegeStats.unlabeledMajors > 0 && (
        <p className="text-xs text-muted-foreground px-1">
          另有 {collegeStats.unlabeledMajors} 个专业尚未标注学院，专业 Tab 中归入「未标注学院」
        </p>
      )}

      {(onGoMajors || onGoScores) && (
        <div className="flex flex-wrap gap-2">
          {onGoMajors && (
            <button
              type="button"
              onClick={onGoMajors}
              className="rounded-lg bg-[#007AFF] px-4 py-2 text-xs font-medium text-white hover:bg-[#007AFF]/90"
            >
              查看全部专业
            </button>
          )}
          {onGoScores && (
            <button
              type="button"
              onClick={onGoScores}
              className="rounded-lg border border-border px-4 py-2 text-xs font-medium hover:bg-muted/50"
            >
              查看分数
            </button>
          )}
        </div>
      )}

      <Section title="基本信息">
        <InfoRow icon={<MapPin className="size-3.5 text-muted-foreground" />} label="所在地">
          {university.province}·{university.city}
        </InfoRow>
        {university.address && (
          <InfoRow label="校区地址">{university.address}</InfoRow>
        )}
        {university.school_type && (
          <InfoRow label="院校类型">{university.school_type}</InfoRow>
        )}
        {tags.length > 0 && (
          <InfoRow label="院校层次">
            <span className="flex flex-wrap gap-1">
              {tags.map((t) => (
                <span key={t} className="rounded bg-[#007AFF]/10 border border-[#007AFF]/15 px-1.5 py-px text-xs text-[#007AFF] font-medium">
                  {t}
                </span>
              ))}
            </span>
          </InfoRow>
        )}
        {degreeTypes.length > 0 && (
          <InfoRow label="学位类别">{degreeTypes.join(" / ")}</InfoRow>
        )}
        {studyModes.length > 0 && (
          <InfoRow label="学习方式">{studyModes.join(" / ")}</InfoRow>
        )}
      </Section>

      {intro && (
        <Section title="院校简介">
          <p className={cn("text-sm text-muted-foreground leading-relaxed", !introExpanded && "line-clamp-4")}>
            {intro}
          </p>
          <button
            onClick={() => setIntroExpanded((v) => !v)}
            className="mt-1.5 flex items-center gap-0.5 text-xs font-medium text-[#007AFF]"
          >
            {introExpanded ? <><ChevronUp className="size-3" />收起</> : <><ChevronDown className="size-3" />展开全文</>}
          </button>
        </Section>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <h3 className="border-b border-border px-4 py-2.5 text-sm font-semibold">{title}</h3>
      <div className="px-4 py-3">{children}</div>
    </div>
  );
}

function InfoRow({ label, icon, children }: { label: string; icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 py-1.5 text-sm">
      {icon}
      <span className="w-20 shrink-0 text-xs text-muted-foreground">{label}</span>
      <span className="flex-1 text-sm text-foreground">{children}</span>
    </div>
  );
}
