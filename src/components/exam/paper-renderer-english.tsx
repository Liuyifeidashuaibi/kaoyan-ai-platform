"use client";

import { useCallback, useMemo, useState } from "react";
import { Download, LayoutGrid, AlignJustify, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { PaperToolbar } from "@/components/exam/paper-toolbar";
import { PaperQuestionCard } from "@/components/exam/paper-question-card";
import { WordLearningProvider } from "@/components/en-learn/word-learning-layer";
import type { ExamPaper, ExamQuestion, ExamVocabulary } from "@/lib/api/types";
import { exportExamVocabulary } from "@/lib/api/exam";

type BilingualMode = "paragraph" | "sidebyside";

type PaperRendererEnglishProps = {
  paper: ExamPaper;
  onTitleChange?: (title: string) => void;
  onAskQuestion?: (question: ExamQuestion) => void;
};

/**
 * 英语试卷渲染模板 — 逐段对照 / 左右分栏双语模式。
 */
export function PaperRendererEnglish({
  paper,
  onTitleChange,
  onAskQuestion,
}: PaperRendererEnglishProps) {
  const [bilingualMode, setBilingualMode] = useState<BilingualMode>("paragraph");
  const [title, setTitle] = useState(paper.title);
  const [exporting, setExporting] = useState(false);
  const [exportDone, setExportDone] = useState(false);

  const analysis = paper.analysis_result;
  const questions = analysis?.questions ?? [];
  const vocabulary = analysis?.vocabulary ?? [];

  // 按 section 分组
  const sections = useMemo(() => {
    const map = new Map<string, ExamQuestion[]>();
    for (const q of questions) {
      const key = q.section_title || "Other";
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(q);
    }
    return Array.from(map.entries()).map(([title, qs]) => ({ title, questions: qs }));
  }, [questions]);

  const wordCount = useMemo(
    () => questions.reduce((acc, q) => acc + (q.stem?.length ?? 0), 0),
    [questions]
  );

  const handleTitleChange = useCallback(
    (newTitle: string) => {
      setTitle(newTitle);
      onTitleChange?.(newTitle);
    },
    [onTitleChange]
  );

  async function handleExportVocabulary() {
    if (!paper.id) return;
    setExporting(true);
    try {
      const data = await exportExamVocabulary(paper.id);
      // 下载为文本文件
      const lines = data.vocabulary.map(
        (v: ExamVocabulary) =>
          `${v.word}\t${v.phonetic ?? ""}\t${v.definition ?? ""}`
      );
      const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${title}-vocabulary.txt`;
      a.click();
      URL.revokeObjectURL(url);
      setExportDone(true);
    } catch {
      // 静默失败
    } finally {
      setExporting(false);
    }
  }

  const stats = `${questions.length} 题 · ${wordCount} 词`;

  return (
    <WordLearningProvider enabled>
      <div className="flex h-full flex-col overflow-hidden rounded-lg border bg-card">
        <PaperToolbar
          title={title}
          onTitleChange={handleTitleChange}
          stats={stats}
          actions={
            <>
              {/* 双语模式切换 */}
              <div className="flex rounded-md border p-0.5">
                <button
                  type="button"
                  className={cn(
                    "rounded px-2 py-1 text-xs transition-colors",
                    bilingualMode === "paragraph"
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                  onClick={() => setBilingualMode("paragraph")}
                >
                  <AlignJustify className="inline size-3.5" /> 逐段
                </button>
                <button
                  type="button"
                  className={cn(
                    "rounded px-2 py-1 text-xs transition-colors",
                    bilingualMode === "sidebyside"
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                  onClick={() => setBilingualMode("sidebyside")}
                >
                  <LayoutGrid className="inline size-3.5" /> 分栏
                </button>
              </div>

              {/* 生词导出 */}
              {vocabulary.length > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 gap-1 text-xs"
                  disabled={exporting}
                  onClick={() => void handleExportVocabulary()}
                >
                  {exporting ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : exportDone ? (
                    "已导出"
                  ) : (
                    <>
                      <Download className="size-3.5" />
                      生词 ({vocabulary.length})
                    </>
                  )}
                </Button>
              )}
            </>
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

                  <div className="space-y-4">
                    {section.questions.map((q, qIdx) =>
                      bilingualMode === "sidebyside" ? (
                        <SideBySideCard
                          key={q.id || qIdx}
                          question={q}
                          displayIndex={qIdx + 1}
                          onAsk={onAskQuestion}
                        />
                      ) : (
                        <ParagraphCard
                          key={q.id || qIdx}
                          question={q}
                          displayIndex={qIdx + 1}
                          onAsk={onAskQuestion}
                        />
                      )
                    )}
                  </div>
                </section>
              ))}
            </div>
          )}
        </div>
      </div>
    </WordLearningProvider>
  );
}

/** 逐段对照卡片 */
function ParagraphCard({
  question,
  displayIndex,
  onAsk,
}: {
  question: ExamQuestion;
  displayIndex: number;
  onAsk?: (q: ExamQuestion) => void;
}) {
  return (
    <div className="rounded-lg border bg-card">
      <div className="flex items-start gap-3 px-4 py-3">
        <span className="text-muted-foreground mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium">
          {displayIndex}
        </span>
        <div className="min-w-0 flex-1 space-y-2">
          {/* 英文原文 */}
          <p className="text-sm leading-relaxed">{question.stem}</p>
          {/* 译文 */}
          {question.stem_translated && (
            <p className="text-muted-foreground text-sm leading-relaxed">
              {question.stem_translated}
            </p>
          )}
          {/* 选项 */}
          {question.options.length > 0 && (
            <div className="space-y-1 pt-1">
              {question.options.map((opt, i) => {
                const translated = question.options_translated?.[i];
                return (
                  <div key={i} className="pl-2">
                    <span className="text-sm">{opt}</span>
                    {translated && (
                      <span className="text-muted-foreground ml-2 text-sm">
                        {translated}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
      {onAsk && (
        <div className="flex justify-end border-t px-3 py-1.5">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs"
            onClick={() => onAsk(question)}
          >
            提问
          </Button>
        </div>
      )}
    </div>
  );
}

/** 左右分栏卡片 */
function SideBySideCard({
  question,
  displayIndex,
  onAsk,
}: {
  question: ExamQuestion;
  displayIndex: number;
  onAsk?: (q: ExamQuestion) => void;
}) {
  return (
    <div className="rounded-lg border bg-card">
      <div className="flex items-start gap-2 border-b px-3 py-1.5">
        <span className="text-muted-foreground flex size-5 shrink-0 items-center justify-center rounded-full bg-muted text-[11px] font-medium">
          {displayIndex}
        </span>
        <span className="text-muted-foreground text-xs">{question.type}</span>
      </div>
      <div className="grid grid-cols-1 gap-px bg-border sm:grid-cols-2">
        <div className="bg-card p-3">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            English
          </p>
          <p className="mt-1 text-sm leading-relaxed">{question.stem}</p>
          {question.options.length > 0 && (
            <div className="mt-2 space-y-1">
              {question.options.map((opt, i) => (
                <div key={i} className="text-sm">{opt}</div>
              ))}
            </div>
          )}
        </div>
        <div className="bg-card p-3">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            中文
          </p>
          <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
            {question.stem_translated || "—"}
          </p>
          {question.options_translated && question.options_translated.length > 0 && (
            <div className="mt-2 space-y-1">
              {question.options_translated.map((opt, i) => (
                <div key={i} className="text-muted-foreground text-sm">{opt}</div>
              ))}
            </div>
          )}
        </div>
      </div>
      {onAsk && (
        <div className="flex justify-end border-t px-3 py-1.5">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs"
            onClick={() => onAsk(question)}
          >
            提问
          </Button>
        </div>
      )}
    </div>
  );
}
