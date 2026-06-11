"use client";

import { useEffect, useRef, useState } from "react";
import { ImagePlus } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { WrongQuestionCategory } from "@/lib/api/types";

type UploadDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  categories: WrongQuestionCategory[];
  /** 从某个科目文件夹内打开时，锁定分类 */
  lockedCategory?: WrongQuestionCategory | null;
  onUpload: (params: {
    file: File;
    categoryId?: number;
    categoryName?: string;
    title: string;
    notes: string;
  }) => Promise<void>;
};

export function UploadDialog({
  open,
  onOpenChange,
  categories,
  lockedCategory,
  onUpload,
}: UploadDialogProps) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [categoryId, setCategoryId] = useState<string>("");
  const [newCategory, setNewCategory] = useState("");
  const [useNewCategory, setUseNewCategory] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    if (lockedCategory) {
      setCategoryId(String(lockedCategory.id));
      setUseNewCategory(false);
      return;
    }
    if (categories.length === 0) {
      setUseNewCategory(true);
      setCategoryId("");
    } else {
      setUseNewCategory(false);
      setCategoryId(String(categories[0].id));
    }
  }, [open, lockedCategory, categories]);

  const reset = () => {
    setFile(null);
    setPreview(null);
    setTitle("");
    setNotes("");
    setCategoryId("");
    setNewCategory("");
    setUseNewCategory(categories.length === 0);
    setError(null);
  };

  const handleFile = (f: File) => {
    setFile(f);
    setPreview(URL.createObjectURL(f));
    if (!title.trim()) {
      setTitle(f.name.replace(/\.[^.]+$/, "") || "未命名错题");
    }
  };

  const handleSubmit = async () => {
    if (!file) return;

    const resolvedCategoryId = lockedCategory
      ? lockedCategory.id
      : useNewCategory
        ? undefined
        : Number(categoryId) || undefined;
    const resolvedCategoryName = lockedCategory
      ? undefined
      : useNewCategory
        ? newCategory.trim()
        : undefined;

    if (!lockedCategory && !resolvedCategoryId && !resolvedCategoryName) {
      setError("请选择或新建科目文件夹");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await onUpload({
        file,
        categoryId: resolvedCategoryId,
        categoryName: resolvedCategoryName,
        title: title.trim() || "未命名错题",
        notes,
      });
      reset();
      onOpenChange(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "上传失败，请重试");
    } finally {
      setSubmitting(false);
    }
  };

  const canSubmit =
    !!file &&
    (lockedCategory ||
      (useNewCategory ? !!newCategory.trim() : !!categoryId));

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) reset();
        onOpenChange(v);
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {lockedCategory
              ? `上传到「${lockedCategory.name}」`
              : "上传错题图片"}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleFile(f);
              }}
            />
            {preview ? (
              <button
                type="button"
                className="block w-full"
                onClick={() => fileRef.current?.click()}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={preview}
                  alt="预览"
                  className="max-h-44 w-full rounded-lg border object-contain"
                />
              </button>
            ) : (
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                className="flex h-36 w-full flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border text-muted-foreground hover:bg-muted/50"
              >
                <ImagePlus className="size-8" />
                <span className="text-sm">点击选择错题图片</span>
              </button>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="wq-title">命名</Label>
            <Input
              id="wq-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="如：极限求导第 3 题"
            />
          </div>

          {!lockedCategory && (
            <div className="space-y-2">
              <Label>科目文件夹</Label>
              {!useNewCategory ? (
                <select
                  value={categoryId}
                  onChange={(e) => setCategoryId(e.target.value)}
                  className="h-9 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm"
                >
                  <option value="">选择科目...</option>
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              ) : (
                <Input
                  placeholder="新建科目，如：高等数学、英语"
                  value={newCategory}
                  onChange={(e) => setNewCategory(e.target.value)}
                />
              )}
              <button
                type="button"
                className="text-xs text-primary underline"
                onClick={() => setUseNewCategory(!useNewCategory)}
              >
                {useNewCategory ? "选择已有科目" : "新建科目文件夹"}
              </button>
            </div>
          )}

          {lockedCategory && (
            <p className="text-sm text-muted-foreground">
              将保存到科目：<span className="font-medium text-foreground">{lockedCategory.name}</span>
            </p>
          )}

          <div className="space-y-2">
            <Label htmlFor="wq-notes">介绍</Label>
            <Textarea
              id="wq-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="记录题目要点、易错点、解题思路..."
              rows={4}
            />
          </div>

          {error ? (
            <p className="text-sm text-destructive">{error}</p>
          ) : null}
        </div>

        <DialogFooter>
          <Button onClick={handleSubmit} disabled={submitting || !canSubmit}>
            {submitting ? "上传中..." : "保存到错题本"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
