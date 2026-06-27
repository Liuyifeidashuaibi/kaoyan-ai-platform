"use client";

import { memo, useState } from "react";
import {
  Check,
  ChevronDown,
  FileSpreadsheet,
  FileText,
  Globe,
  LayoutTemplate,
  Loader2,
  Search,
  ShieldCheck,
  Sparkles,
  Table2,
  Wand2,
  Wrench,
} from "lucide-react";

import type { AgentFile, AgentStep } from "@/lib/api/types";
import { resolveUploadUrl } from "@/lib/config/api";
import { cn } from "@/lib/utils";

/* ── 工具名称映射 ───────────────────────────────────────── */
const TOOL_LABELS: Record<string, string> = {
  // 文档工具
  read_document: "读取文档",
  export_document: "导出文档",
  export_excel: "导出表格",
  format_document: "格式化文档",
  // 数据工具
  analyze_data: "数据分析",
  clean_data: "数据清洗",
  convert_format: "格式转换",
  // 检索工具
  search_knowledge: "知识库检索",
  web_search: "联网搜索",
  // 模板工具
  search_template: "模板检索",
  validate_format: "格式校验",
  // 系统工具
  create_task_plan: "任务规划",
};

function getToolIcon(tool: string) {
  switch (tool) {
    case "export_document":
    case "read_document":
    case "format_document":
      return FileText;
    case "export_excel":
      return FileSpreadsheet;
    case "analyze_data":
      return Table2;
    case "clean_data":
    case "convert_format":
      return Wand2;
    case "search_knowledge":
      return Search;
    case "web_search":
      return Globe;
    case "search_template":
      return LayoutTemplate;
    case "validate_format":
      return ShieldCheck;
    case "create_task_plan":
      return Sparkles;
    default:
      return Wrench;
  }
}

function getToolLabel(tool: string): string {
  return TOOL_LABELS[tool] ?? tool;
}

/* ── 单个步骤行 ─────────────────────────────────────────── */
const StepItem = memo(function StepItem({ step }: { step: AgentStep }) {
  const [expanded, setExpanded] = useState(false);
  const Icon = getToolIcon(step.tool);
  const isRunning = step.status === "running";

  // 生成参数摘要
  const argSummary = (() => {
    if (step.tool === "export_document") {
      const title = step.args.title as string | undefined;
      const format = (step.args.format as string | undefined) ?? "pdf";
      return `${title ?? "文档"} · ${format.toUpperCase()}`;
    }
    if (step.tool === "export_excel") {
      const title = step.args.title as string | undefined;
      return title ?? "表格";
    }
    if (
      step.tool === "search_knowledge" ||
      step.tool === "web_search" ||
      step.tool === "search_template"
    ) {
      return (step.args.query as string | undefined) ?? "";
    }
    if (step.tool === "read_document") {
      return (step.args.file_path as string | undefined) ?? "";
    }
    if (step.tool === "validate_format") {
      const tid = step.args.template_id;
      return tid ? `模板 #${tid}` : "";
    }
    if (step.tool === "create_task_plan") {
      return (step.args.task_description as string | undefined) ?? "";
    }
    return JSON.stringify(step.args).slice(0, 60);
  })();

  // 生成结果摘要
  const resultSummary = (() => {
    if (!step.result) return null;
    if (step.result.error) return `错误: ${step.result.error}`;
    if (
      (step.tool === "export_document" || step.tool === "export_excel") &&
      step.result.filename
    ) {
      return `已生成 ${step.result.filename}`;
    }
    if (step.result.summary) {
      return step.result.summary as string;
    }
    if (step.tool === "validate_format") {
      const passed = step.result.passed as boolean | undefined;
      const failed = step.result.failed_count as number | undefined;
      if (passed === true) return "校验通过";
      if (passed === false) return `${failed ?? 0} 项不通过`;
    }
    return null;
  })();

  return (
    <div className="rounded-lg border border-border bg-muted/30 text-xs">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-muted/50 transition-colors"
      >
        <span
          className={cn(
            "flex size-4 shrink-0 items-center justify-center",
            isRunning ? "text-primary" : "text-green-500"
          )}
        >
          {isRunning ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <Check className="size-3.5" />
          )}
        </span>
        <Icon className="size-3.5 shrink-0 text-muted-foreground" />
        <span className="font-medium text-foreground">
          {getToolLabel(step.tool)}
        </span>
        {argSummary && (
          <span className="truncate text-muted-foreground">{argSummary}</span>
        )}
        {resultSummary && (
          <span
            className={cn(
              "truncate",
              step.result?.error
                ? "text-red-500"
                : "text-green-600 dark:text-green-400"
            )}
          >
            → {resultSummary}
          </span>
        )}
        <ChevronDown
          className={cn(
            "ml-auto size-3.5 shrink-0 text-muted-foreground/50 transition-transform",
            expanded && "rotate-180"
          )}
        />
      </button>

      {expanded && (
        <div className="border-t border-border px-3 py-2 space-y-1.5">
          <div>
            <span className="text-muted-foreground/60">参数: </span>
            <code className="text-foreground/80">
              {JSON.stringify(step.args, null, 2)}
            </code>
          </div>
          {step.result && (
            <div>
              <span className="text-muted-foreground/60">结果: </span>
              <code className="text-foreground/80">
                {JSON.stringify(step.result, null, 2)}
              </code>
            </div>
          )}
        </div>
      )}
    </div>
  );
});

/* ── 步骤列表 ───────────────────────────────────────────── */
type AgentStepListProps = {
  steps: AgentStep[];
};

export function AgentStepList({ steps }: AgentStepListProps) {
  if (!steps.length) return null;

  return (
    <div className="mb-2 space-y-1.5">
      {steps.map((step, i) => (
        <StepItem key={`${step.step_id}-${i}`} step={step} />
      ))}
    </div>
  );
}

/* ── 文件下载卡片 ───────────────────────────────────────── */
type AgentFileListProps = {
  files: AgentFile[];
};

export function AgentFileList({ files }: AgentFileListProps) {
  if (!files.length) return null;

  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {files.map((file, i) => {
        const url = resolveUploadUrl(file.file_url);
        const sizeKb = (file.file_size / 1024).toFixed(1);
        return (
          <a
            key={i}
            href={url}
            download={file.filename}
            className="group flex items-center gap-2.5 rounded-xl border border-border bg-muted/40 px-3 py-2 transition-colors hover:bg-muted hover:border-primary/30"
          >
            <FileText className="size-4 text-primary" />
            <div className="flex flex-col">
              <span className="text-xs font-medium text-foreground">
                {file.title || file.filename}
              </span>
              <span className="text-[10px] text-muted-foreground">
                {file.format.toUpperCase()} · {sizeKb} KB
              </span>
            </div>
          </a>
        );
      })}
    </div>
  );
}
