"use client";

import { useRouter } from "next/navigation";
import { Loader2, MessageSquare, Sparkles } from "lucide-react";

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
import type { WrongQuestion } from "@/lib/api/types";
import { resolveUploadUrl } from "@/lib/config/api";

type QuestionDetailDialogProps = {
  question: WrongQuestion | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAnalyze: (id: number) => Promise<void>;
  onStartChat: (id: number) => Promise<string>;
  onUpdateNotes: (id: number, notes: string) => Promise<void>;
  analyzing?: boolean;
  startingChat?: boolean;
};

export function QuestionDetailDialog({
  question,
  open,
  onOpenChange,
  onAnalyze,
  onStartChat,
  onUpdateNotes,
  analyzing,
  startingChat,
}: QuestionDetailDialogProps) {
  const router = useRouter();

  if (!question) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            {question.title}
            <Badge variant="secondary">{question.category_name}</Badge>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={resolveUploadUrl(question.image_path)}
            alt={question.title}
            className="w-full rounded-lg border object-contain"
          />

          <div className="space-y-2">
            <p className="text-sm font-medium">介绍</p>
            <Textarea
              defaultValue={question.notes}
              rows={4}
              onBlur={(e) => {
                if (e.target.value !== question.notes) {
                  onUpdateNotes(question.id, e.target.value);
                }
              }}
            />
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
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
