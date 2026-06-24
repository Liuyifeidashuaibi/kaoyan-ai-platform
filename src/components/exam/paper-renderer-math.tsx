"use client";

import { useCallback, useMemo, useState } from "react";
import { Eye, EyeOff, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { PaperToolbar } from "@/components/exam/paper-toolbar";
import { PaperQuestionCard } from "@/components/exam/paper-question-card";
import { favoriteExamQuestions } from "@/lib/api/exam";
import type { ExamPaper, ExamQuestion } from "@/lib/api/types";

type PaperRendererMathProps = {
  paper: ExamPaper;
  onTitleChange?: (title: string) => void;
  onAskQuestion?: (question: ExamQuestion) => void;
  /** LaTeX 渲染器 (可选, 复用 chat-markdown-content) */
  renderLatex?: (text: string) => React.ReactNode;
};

/**
 * 数学试卷渲染模板 — 选择/填空/解答分区，答案折叠，考点标签。
 */
export function PaperRendererMath({
  paper,
  onTitleChange,
  onAskQuestion,
  renderLatex,
}: PaperRendererMathProps) {
  const [title, setTitle] = useState(paper.title);
  const [showAllAnswers, setShowAllAnswers] = useState(false);
  const [favLoading, setFavLoading] = useState(false);

  const analysis = paper.analysis_result;
  const questions = analysis?.questions ?? [];

  // 按题型分组
  const sections = useMemo(() => {
    const typeMap: Record<string, string> = {
      choice: "选择题",
      fill: "填空题",
      solution: "解答题",
      other: "其他",
    };
    const map = new Map<string, ExamQuestion[]>();
    for (const q of questions) {
      const key = q.type || "other";
      const label = typeMap[key] || q.section_title || "其他";
      if (!map.has(label)) map.set(label, []);
      map.get(label)!.push(q);
    }
    return Array.from(map.entries()).map(([title, qs]) => ({
      title,
      questions: qs,
    }));
  }, [questions]);

  const stats = useMemo(() => {
    const counts = sections.map((s) => `${s.title} ${s.questions.length}`).join(" · ");
    return `${questions.length} 题${counts ? ` (${counts})` : ""}`;
  }, [questions, sections]);

  const handleTitleChange = useCallback(
    (newTitle: string) => {
      setTitle(newTitle);
      onTitleChange?.(newTitle);
    },
    [onTitleChange]
  );

  async function handleFavorite(q: ExamQuestion) {
    if (!paper.id || !q.id) return;
    setFavLoading(true);
    try {
      await favoriteExamQuestions(paper.id, [q.id], paper.subject);
    } catch {
      // 静默
    } finally {
      setFavLoading(false);
    }
  }

  const renderContent = renderLatex ?? ((text: string) => text);

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-lg border bg-card">
      <PaperToolbar
        title={title}
        onTitleChange={handleTitleChange}
        stats={stats}
        actions={
          <Button
            variant="outline"
            size="sm"
            className="h-7 gap-1 text-xs"
            onClick={() => setShowAllAnswers((v) => !v)}
          >
            {showAllAnswers ? (
              <>
                <EyeOff className="size-3.5" /> 隐藏答案
              </>
            ) : (
              <>
                <Eye className="size-3.5" /> 显示答案
              </>
            )}
          </Button>
        }
      />

      {/* 正文 */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {sections.length === 0 ? (
          <div className="text-muted-foreground flex h-full items-center justify-center text-sm">
            暂无解析结果
          </div>
        ) : (
          <div className="space-y-6">
            {sections.map((section, sIdx) => (
              <section key={sIdx}>
                <h3 className="mb-3 text-sm font-semibold tracking-wide">
                  {section.title}
                </h3>
                <Separator className="mb-3" />
                <div className="space-y-3">
                  {section.questions.map((q, qIdx) => (
                    <PaperQuestionCard
                      key={q.id || qIdx}
                      question={q}
                      displayIndex={qIdx + 1}
                      defaultExpanded={showAllAnswers}
                      renderStem={(s) => renderContent(s)}
                      renderAnalysis={(s) => renderContent(s)}
                      onAsk={onAskQuestion}
                      onFavorite={handleFavorite}
                    />
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}
      </div>

      {favLoading && (
        <div className="text-muted-foreground flex items-center gap-1 border-t px-4 py-1.5 text-xs">
          <Loader2 className="size-3 animate-spin" />
          收藏中...
        </div>
      )}
    </div>
  );
}
