"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Download,
  ExternalLink,
  Globe,
  Loader2,
  Lock,
  MessageSquare,
  Sparkles,
  ZoomIn,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { ImageViewer } from "@/components/wrong-questions/image-viewer";
import type { WrongQuestion } from "@/lib/api/types";
import { resolveUploadUrl } from "@/lib/config/api";
import {
  getMaterialPath,
  isPdfDocument,
  isPreviewableAudio,
  isPreviewableImage,
  isPreviewableVideo,
  MATERIAL_TYPE_LABELS,
} from "@/lib/wrong-questions/material-utils";

type QuestionDetailDialogProps = {
  question: WrongQuestion | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAnalyze: (id: number) => Promise<void>;
  onStartChat: (id: number) => Promise<string>;
  onUpdateNotes: (id: number, notes: string) => Promise<void>;
  onTogglePublic?: (id: number, isPublic: boolean) => Promise<void>;
  readOnly?: boolean;
  analyzing?: boolean;
  startingChat?: boolean;
};

function MaterialPreview({ question }: { question: WrongQuestion }) {
  const path = resolveUploadUrl(getMaterialPath(question));
  const type = question.file_type;

  if (isPreviewableImage(type)) {
    return (
      /* eslint-disable-next-line @next/next/no-img-element */
      <img
        src={path}
        alt={question.title}
        className="w-full object-contain"
      />
    );
  }

  if (isPreviewableVideo(type)) {
    return (
      <video
        src={path}
        controls
        className="max-h-[360px] w-full rounded-lg bg-black object-contain"
      />
    );
  }

  if (isPreviewableAudio(type)) {
    return (
      <div className="rounded-lg border bg-muted/40 p-6">
        <audio src={path} controls className="w-full" />
      </div>
    );
  }

  if (isPdfDocument(type, question.original_filename)) {
    return (
      <iframe
        src={path}
        title={question.title}
        className="h-[420px] w-full rounded-lg border bg-white"
      />
    );
  }

  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border bg-muted/40 px-6 py-10 text-center">
      <p className="text-sm text-muted-foreground">
        {MATERIAL_TYPE_LABELS[type]} ·{" "}
        {question.original_filename || question.title}
      </p>
      <Button asChild variant="outline" size="sm">
        <a href={path} target="_blank" rel="noopener noreferrer">
          <ExternalLink className="size-4" />
          在新窗口打开
        </a>
      </Button>
      <Button asChild variant="secondary" size="sm">
        <a href={path} download={question.original_filename || undefined}>
          <Download className="size-4" />
          下载文件
        </a>
      </Button>
    </div>
  );
}

export function QuestionDetailDialog({
  question,
  open,
  onOpenChange,
  onAnalyze,
  onStartChat,
  onUpdateNotes,
  onTogglePublic,
  readOnly = false,
  analyzing,
  startingChat,
}: QuestionDetailDialogProps) {
  const router = useRouter();
  const [viewerOpen, setViewerOpen] = useState(false);
  const [togglingPublic, setTogglingPublic] = useState(false);

  if (!question) return null;

  const isImage = question.file_type === "image";
  const filePath = getMaterialPath(question);

  async function handleTogglePublic() {
    if (!onTogglePublic) return;
    setTogglingPublic(true);
    try {
      await onTogglePublic(question!.id, !question!.is_public);
    } finally {
      setTogglingPublic(false);
    }
  }

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex flex-wrap items-center gap-2">
              {question.title}
              <Badge variant="secondary">{question.category_name}</Badge>
              <Badge variant="outline">
                {MATERIAL_TYPE_LABELS[question.file_type]}
              </Badge>
              {!readOnly && (
                <Badge variant={question.is_public ? "default" : "secondary"}>
                  {question.is_public ? "公开" : "隐私"}
                </Badge>
              )}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {isImage ? (
              <button
                type="button"
                onClick={() => setViewerOpen(true)}
                className="group relative block w-full overflow-hidden rounded-lg border"
                aria-label="点击放大查看（滚轮缩放）"
              >
                <MaterialPreview question={question} />
                <span className="absolute right-2 top-2 flex items-center gap-1 rounded-full bg-black/55 px-2 py-1 text-xs text-white opacity-0 transition-opacity group-hover:opacity-100">
                  <ZoomIn className="size-3.5" />
                  点击放大
                </span>
              </button>
            ) : (
              <MaterialPreview question={question} />
            )}

            <div className="space-y-2">
              <p className="text-sm font-medium">介绍 / 笔记</p>
              {readOnly ? (
                <p className="whitespace-pre-wrap text-sm text-muted-foreground">
                  {question.notes || "暂无笔记"}
                </p>
              ) : (
                <Textarea
                  defaultValue={question.notes}
                  rows={4}
                  onBlur={(e) => {
                    if (e.target.value !== question.notes) {
                      onUpdateNotes(question.id, e.target.value);
                    }
                  }}
                />
              )}
            </div>

            {question.ai_analysis && (
              <div className="space-y-2 rounded-lg bg-muted p-3">
                <p className="flex items-center gap-1 text-sm font-medium">
                  <Sparkles className="size-3.5" />
                  AI 解析
                </p>
                <p className="whitespace-pre-wrap text-sm leading-relaxed">
                  {question.ai_analysis}
                </p>
              </div>
            )}
          </div>

          <DialogFooter className="flex-col gap-2 sm:flex-row">
            {!readOnly && onTogglePublic ? (
              <Button
                variant="outline"
                onClick={handleTogglePublic}
                disabled={togglingPublic}
              >
                {togglingPublic ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : question.is_public ? (
                  <Lock className="size-4" />
                ) : (
                  <Globe className="size-4" />
                )}
                {question.is_public ? "设为隐私" : "设为公开"}
              </Button>
            ) : null}
            {!readOnly && isImage ? (
              <Button
                variant="outline"
                onClick={() => onAnalyze(question.id)}
                disabled={analyzing}
              >
                {analyzing ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Sparkles className="size-4" />
                )}
                {question.ai_analysis ? "重新解析" : "AI 解析"}
              </Button>
            ) : null}
            {!readOnly ? (
            <Button
              onClick={async () => {
                const sessionId = await onStartChat(question.id);
                onOpenChange(false);
                router.push(`/chat?session=${sessionId}&autoReply=1`);
              }}
              disabled={startingChat}
            >
              {startingChat ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <MessageSquare className="size-4" />
              )}
              一键发起新聊天
            </Button>
            ) : null}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {isImage ? (
        <ImageViewer
          open={viewerOpen}
          index={0}
          slides={[
            {
              src: resolveUploadUrl(filePath),
              title: question.title,
              description: question.category_name,
            },
          ]}
          onClose={() => setViewerOpen(false)}
        />
      ) : null}
    </>
  );
}
