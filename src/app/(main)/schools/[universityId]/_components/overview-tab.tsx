"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, ExternalLink, MapPin } from "lucide-react";
import { cn } from "@/lib/utils";
import { getUniversityLevelTags, type University, type Major } from "@/lib/api/schools";

interface OverviewTabProps {
  university: University;
  majors: Major[];
}

export function OverviewTab({ university, majors }: OverviewTabProps) {
  const [introExpanded, setIntroExpanded] = useState(false);
  const intro = university.intro ?? "";
  const tags = getUniversityLevelTags(university);

  const colleges = [...new Set(majors.map((m) => m.college).filter(Boolean))] as string[];
  const degreeTypes = [...new Set(majors.map((m) => m.degree_type).filter(Boolean))] as string[];
  const studyModes = [...new Set(majors.map((m) => m.study_mode).filter(Boolean))] as string[];
  const totalEnrollment = majors.reduce((s, m) => s + (m.enrollment_count ?? 0), 0);

  return (
    <div className="space-y-3 p-4">
      {/* 招生数据概览 */}
      <div className="grid grid-cols-3 gap-2">
        {[
          { label: "招生专业", value: majors.length, unit: "个" },
          { label: "开设学院", value: colleges.length, unit: "个" },
          { label: "拟招生", value: totalEnrollment || "—", unit: totalEnrollment ? "人" : "" },
        ].map((item) => (
          <div
            key={item.label}
            className="flex flex-col items-center rounded-xl border border-border bg-card py-3"
          >
            <p className="text-xl font-bold text-orange-500 leading-none">
              {item.value}
              <span className="text-xs font-normal text-muted-foreground">{item.unit}</span>
            </p>
            <p className="mt-1 text-xs text-muted-foreground">{item.label}</p>
          </div>
        ))}
      </div>

      {/* 基本信息 */}
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
                <span key={t} className="rounded bg-orange-50 border border-orange-100 px-1.5 py-px text-xs text-orange-700 font-medium">
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
        {university.website && (
          <InfoRow label="官方网站">
            <a
              href={university.website}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-orange-500 underline-offset-2 hover:underline text-xs"
            >
              访问官网 <ExternalLink className="size-3" />
            </a>
          </InfoRow>
        )}
      </Section>

      {/* 院校简介 */}
      {intro && (
        <Section title="院校简介">
          <p className={cn("text-sm text-muted-foreground leading-relaxed", !introExpanded && "line-clamp-4")}>
            {intro}
          </p>
          <button
            onClick={() => setIntroExpanded((v) => !v)}
            className="mt-1.5 flex items-center gap-0.5 text-xs font-medium text-orange-500"
          >
            {introExpanded ? <><ChevronUp className="size-3" />收起</> : <><ChevronDown className="size-3" />展开全文</>}
          </button>
        </Section>
      )}

      {/* 开设学院 */}
      {colleges.length > 0 && (
        <Section title="开设学院">
          <div className="flex flex-wrap gap-1.5">
            {colleges.map((c) => (
              <span key={c} className="rounded-lg border border-border bg-muted px-2.5 py-1 text-xs">
                {c}
              </span>
            ))}
          </div>
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
