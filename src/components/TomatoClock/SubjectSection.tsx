"use client";

import { useState } from "react";
import { Trash2 } from "lucide-react";

import { ConfirmDialog } from "@/components/TomatoClock/ConfirmDialog";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { Subject } from "@/components/TomatoClock/types";
import { cn } from "@/lib/utils";

interface SubjectSectionProps {
  subjects: Subject[];
  selectedSubjectId: string | null;
  subjectLocked: boolean;
  onSelect: (subjectId: string) => void;
  onAdd: (name: string) => boolean;
  onRemove: (subjectId: string) => void;
}

export function SubjectSection({
  subjects,
  selectedSubjectId,
  subjectLocked,
  onSelect,
  onAdd,
  onRemove,
}: SubjectSectionProps) {
  const [draft, setDraft] = useState("");
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  const trimmed = draft.trim();
  const canAdd = trimmed.length >= 1 && trimmed.length <= 20;
  const pendingSubject = subjects.find((item) => item.id === pendingDeleteId);

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>番茄钟科目</CardTitle>
          <CardDescription>
            添加科目并点击选择，计时完成后时长累计到对应科目
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form
            className="flex flex-col gap-3 sm:flex-row"
            onSubmit={(event) => {
              event.preventDefault();
              if (!canAdd) {
                return;
              }
              if (onAdd(trimmed)) {
                setDraft("");
              }
            }}
          >
            <Input
              value={draft}
              maxLength={20}
              placeholder="输入科目名称"
              disabled={subjectLocked}
              onChange={(event) => setDraft(event.target.value)}
            />
            <Button
              type="submit"
              disabled={!canAdd || subjectLocked}
              className="sm:w-28"
            >
              添加
            </Button>
          </form>

          {subjects.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              暂无科目，请先添加一个番茄钟科目
            </p>
          ) : (
            <ul className="divide-y divide-border rounded-lg border border-border">
              {subjects.map((subject) => {
                const selected = subject.id === selectedSubjectId;
                return (
                  <li
                    key={subject.id}
                    className={cn(
                      "flex items-center justify-between gap-3 px-4 py-3",
                      selected && "bg-primary/5"
                    )}
                  >
                    <button
                      type="button"
                      disabled={subjectLocked && !selected}
                      className={cn(
                        "flex min-w-0 flex-1 items-center gap-2 text-left",
                        subjectLocked && !selected && "cursor-not-allowed opacity-50"
                      )}
                      onClick={() => {
                        if (!subjectLocked) {
                          onSelect(subject.id);
                        }
                      }}
                    >
                      <span
                        className="size-2.5 shrink-0 rounded-full"
                        style={{ backgroundColor: subject.color }}
                        aria-hidden
                      />
                      <span
                        className={cn(
                          "truncate font-medium",
                          selected && "text-primary"
                        )}
                      >
                        {subject.name}
                      </span>
                    </button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      disabled={subjectLocked}
                      className="shrink-0 text-destructive hover:text-destructive"
                      aria-label={`删除科目 ${subject.name}`}
                      onClick={() => setPendingDeleteId(subject.id)}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={pendingDeleteId !== null}
        title="确认删除科目？"
        description={
          pendingSubject
            ? `将删除「${pendingSubject.name}」及其全部番茄钟记录，此操作不可恢复。`
            : "此操作不可恢复。"
        }
        confirmLabel="确认删除"
        onOpenChange={(open) => {
          if (!open) {
            setPendingDeleteId(null);
          }
        }}
        onConfirm={() => {
          if (pendingDeleteId) {
            onRemove(pendingDeleteId);
          }
          setPendingDeleteId(null);
        }}
      />
    </>
  );
}
