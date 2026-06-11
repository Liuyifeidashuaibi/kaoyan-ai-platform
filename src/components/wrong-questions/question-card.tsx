"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { WrongQuestion } from "@/lib/api/types";
import { resolveUploadUrl } from "@/lib/config/api";

type QuestionCardProps = {
  question: WrongQuestion;
  onClick: () => void;
  onImageClick?: (e: React.MouseEvent) => void;
};

export function QuestionCard({ question, onClick, onImageClick }: QuestionCardProps) {
  return (
    <Card
      className="cursor-pointer transition-shadow hover:shadow-md"
      onClick={onClick}
    >
      <div
        className="aspect-[4/3] overflow-hidden bg-muted"
        onClick={onImageClick}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={resolveUploadUrl(question.image_path)}
          alt={question.title}
          className="size-full object-cover transition-transform hover:scale-105"
        />
      </div>
      <CardContent className="space-y-2 pt-3">
        <p className="truncate font-medium">{question.title}</p>
        {question.notes ? (
          <p className="line-clamp-2 text-xs text-muted-foreground">
            {question.notes}
          </p>
        ) : null}
        <div className="flex items-center justify-between gap-2">
          {question.ai_analysis ? (
            <Badge variant="secondary">已解析</Badge>
          ) : (
            <span className="text-xs text-muted-foreground">点击查看</span>
          )}
          <span className="text-xs text-muted-foreground">
            {new Date(question.created_at).toLocaleDateString("zh-CN")}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
