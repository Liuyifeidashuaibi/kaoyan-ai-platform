"use client";

import {
  FileAudio,
  FileText,
  FileVideo,
  ImageIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { VideoThumbnail } from "@/components/wrong-questions/video-thumbnail";
import type { WrongQuestion } from "@/lib/api/types";
import { resolveUploadUrl } from "@/lib/config/api";
import {
  formatMaterialTime,
  getMaterialPath,
  MATERIAL_TYPE_LABELS,
} from "@/lib/wrong-questions/material-utils";
import { cn } from "@/lib/utils";

type MaterialTimelineItemProps = {
  question: WrongQuestion;
  onClick: () => void;
  onPreviewClick?: (e: React.MouseEvent) => void;
  isLast?: boolean;
};

function TypeIcon({ type }: { type: WrongQuestion["file_type"] }) {
  const className = "size-4";
  switch (type) {
    case "video":
      return <FileVideo className={className} />;
    case "document":
      return <FileText className={className} />;
    case "audio":
      return <FileAudio className={className} />;
    default:
      return <ImageIcon className={className} />;
  }
}

function MaterialThumb({ question }: { question: WrongQuestion }) {
  const path = getMaterialPath(question);

  if (question.file_type === "image") {
    return (
      /* eslint-disable-next-line @next/next/no-img-element */
      <img
        src={resolveUploadUrl(path)}
        alt={question.title}
        className="size-full object-cover"
      />
    );
  }

  if (question.file_type === "video") {
    return (
      <VideoThumbnail
        src={resolveUploadUrl(path)}
        alt={question.title}
        className="size-full"
      />
    );
  }

  const bg =
    question.file_type === "document"
      ? "bg-blue-500/10 text-blue-600"
      : question.file_type === "audio"
        ? "bg-emerald-500/10 text-emerald-600"
        : "bg-muted text-muted-foreground";

  return (
    <div
      className={cn(
        "flex size-full flex-col items-center justify-center gap-1 px-2 text-center",
        bg
      )}
    >
      <TypeIcon type={question.file_type} />
      <span className="line-clamp-2 text-[10px] leading-tight">
        {question.original_filename || MATERIAL_TYPE_LABELS[question.file_type]}
      </span>
    </div>
  );
}

export function MaterialTimelineItem({
  question,
  onClick,
  onPreviewClick,
  isLast,
}: MaterialTimelineItemProps) {
  return (
    <div className="relative flex gap-4 pb-6">
      {!isLast && (
        <span className="absolute left-[11px] top-8 h-[calc(100%-1rem)] w-px bg-border" />
      )}

      <div className="relative z-10 mt-1 flex size-6 shrink-0 items-center justify-center rounded-full border bg-background">
        <span className="size-2 rounded-full bg-primary" />
      </div>

      <button
        type="button"
        onClick={onClick}
        className="min-w-0 flex-1 rounded-xl border bg-card text-left transition-shadow hover:shadow-md"
      >
        <div className="flex flex-col gap-3 p-3 sm:flex-row sm:items-start">
          <div
            className="aspect-[4/3] w-full shrink-0 overflow-hidden rounded-lg bg-muted sm:w-28"
            onClick={onPreviewClick}
          >
            <MaterialThumb question={question} />
          </div>

          <div className="min-w-0 flex-1 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <p className="truncate font-medium">{question.title}</p>
              <Badge variant="outline" className="shrink-0">
                {MATERIAL_TYPE_LABELS[question.file_type]}
              </Badge>
              {question.ai_analysis ? (
                <Badge variant="secondary" className="shrink-0">
                  Analyzed
                </Badge>
              ) : null}
            </div>

            {question.notes ? (
              <p className="line-clamp-2 text-sm text-muted-foreground">
                {question.notes}
              </p>
            ) : null}

            <p className="text-xs text-muted-foreground">
              {formatMaterialTime(question.created_at)}
            </p>
          </div>
        </div>
      </button>
    </div>
  );
}

/** @deprecated 保留旧名以兼容引用 */
export const QuestionCard = MaterialTimelineItem;
