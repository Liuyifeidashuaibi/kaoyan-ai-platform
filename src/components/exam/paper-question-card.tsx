"use client";

import { useState } from "react";
import {
  Bookmark,
  BookmarkCheck,
  ChevronDown,
  ChevronUp,
  MessageSquare,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ExamQuestion } from "@/lib/api/types";

type PaperQuestionCardProps = {
  question: ExamQuestion;
  /** 渲染题干内容的自定义渲染器（支持 LaTeX 等） */
  renderStem?: (stem: string) => React.ReactNode;
  /** 渲染解析内容的自定义渲染器（支持 LaTeX 等） */
  renderAnalysis?: (text: string) => React.ReactNode;
  /** 追问按钮回调 */
  onAsk?: (question: ExamQuestion) => void;
  /** 收藏按钮回调 */
  onFavorite?: (question: ExamQuestion) => void;
  /** 是否已收藏 */
  isFavorited?: boolean;
  /** 默认展开答案 */
  defaultExpanded?: boolean;
  /** 显示序号 */
  displayIndex?: number;
};

/**
 * 通用单题卡片 — 折叠/展开答案、考点标签、操作按钮。
 */
export function PaperQuestionCard({
  question,
  renderStem,
  renderAnalysis,
  onAsk,
  onFavorite,
  isFavorited: isFav = false,
  defaultExpanded = false,
  displayIndex,
}: PaperQuestionCardProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [localFav, setLocalFav] = useState(isFav);

  const hasAnswer = !!(question.answer || question.analysis);

  function handleFavorite() {
    setLocalFav((v) => !v);
    onFavorite?.(question);
  }

  const idx = displayIndex ?? question.id;

  return (
    <div className="rounded-lg border bg-card transition-shadow hover:shadow-sm">
      {/* 题头 */}
      <div className="flex items-start gap-3 px-4 py-3">
        <span className="text-muted-foreground mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium">
          {idx}
        </span>
        <div className="min-w-0 flex-1 space-y-2">
          {/* 题干 */}
          <div className="text-sm leading-relaxed">
            {renderStem ? renderStem(question.stem) : question.stem}
          </div>

          {/* 选项 */}
          {question.options.length > 0 && (
            <div className="grid grid-cols-1 gap-1.5 pl-2 sm:grid-cols-2">
              {question.options.map((opt, i) => (
                <div
                  key={i}
                  className={cn(
                    "rounded-md px-3 py-1.5 text-sm",
                    "bg-muted/40",
                    // 如果有答案且该选项正确，高亮
                    question.answer &&
                      opt.startsWith(question.answer) &&
                      "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                  )}
                >
                  {opt}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 答案折叠区 */}
      {hasAnswer && (
        <>
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="text-muted-foreground hover:text-foreground flex w-full items-center gap-1 border-t px-4 py-2 text-xs transition-colors"
          >
            {expanded ? (
              <ChevronUp className="size-3.5" />
            ) : (
              <ChevronDown className="size-3.5" />
            )}
            {expanded ? "收起解析" : "查看解析"}
          </button>

          {expanded && (
            <div className="space-y-3 border-t px-4 py-3">
              {/* 答案 */}
              {question.answer && (
                <div>
                  <span className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                    答案
                  </span>
                  <div className="mt-1 text-sm font-medium">
                    {question.answer}
                  </div>
                </div>
              )}

              {/* 解析 */}
              {question.analysis && (
                <div>
                  <span className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                    解析
                  </span>
                  <div className="text-muted-foreground mt-1 text-sm leading-relaxed">
                    {renderAnalysis
                      ? renderAnalysis(question.analysis)
                      : question.analysis}
                  </div>
                </div>
              )}

              {/* 易错点 */}
              {question.common_mistakes && (
                <div>
                  <span className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                    易错点
                  </span>
                  <div className="mt-1 text-sm text-amber-600 dark:text-amber-400">
                    {question.common_mistakes}
                  </div>
                </div>
              )}

              {/* 考点标签 */}
              {question.key_points && (
                <div className="flex flex-wrap gap-1.5">
                  {question.key_points
                    .split(/[,，、;；\n]+/)
                    .filter(Boolean)
                    .map((kp, i) => (
                      <Badge
                        key={i}
                        variant="secondary"
                        className="text-[11px] font-normal"
                      >
                        {kp.trim()}
                      </Badge>
                    ))}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* 底部操作栏 */}
      {(onAsk || onFavorite) && (
        <div className="flex items-center justify-end gap-1 border-t px-3 py-1.5">
          {onAsk && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-1 text-xs"
              onClick={() => onAsk(question)}
            >
              <MessageSquare className="size-3.5" />
              提问
            </Button>
          )}
          {onFavorite && (
            <Button
              variant="ghost"
              size="sm"
              className={cn(
                "h-7 gap-1 text-xs",
                localFav && "text-amber-500"
              )}
              onClick={handleFavorite}
            >
              {localFav ? (
                <BookmarkCheck className="size-3.5" />
              ) : (
                <Bookmark className="size-3.5" />
              )}
              收藏
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
