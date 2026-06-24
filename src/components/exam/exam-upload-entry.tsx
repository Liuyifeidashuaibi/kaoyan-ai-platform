"use client";

import { useCallback, useRef, useState } from "react";
import { Upload, Loader2, FileImage } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { ExamSubject } from "@/lib/api/types";

type ExamUploadEntryProps = {
  subject: ExamSubject;
  onUpload: (file: File, title: string) => void | Promise<void>;
  disabled?: boolean;
};

/**
 * 试卷上传入口组件 — 支持拖拽和点选上传。
 */
export function ExamUploadEntry({
  subject,
  onUpload,
  disabled,
}: ExamUploadEntryProps) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback((f: File | null) => {
    if (!f) return;
    setFile(f);
    setTitle(f.name.replace(/\.[^.]+$/, ""));
    const url = URL.createObjectURL(f);
    setPreview(url);
  }, []);

  function clearFile() {
    if (preview) URL.revokeObjectURL(preview);
    setFile(null);
    setPreview(null);
    setTitle("");
  }

  async function handleSubmit() {
    if (!file) return;
    setUploading(true);
    try {
      await onUpload(file, title || file.name);
    } finally {
      setUploading(false);
    }
  }

  const subjectLabel = subject === "english" ? "英语试卷" : "数学试卷";

  return (
    <div className="flex flex-col gap-4">
      {/* 上传区域 */}
      <div
        className={cn(
          "relative flex min-h-[200px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed transition-colors",
          dragOver
            ? "border-primary bg-primary/5"
            : "border-muted-foreground/25 hover:border-muted-foreground/40",
          disabled && "pointer-events-none opacity-50"
        )}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          const f = e.dataTransfer.files?.[0];
          if (f && f.type.startsWith("image/")) handleFile(f);
        }}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
        />

        {preview ? (
          <div className="relative w-full p-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={preview}
              alt="preview"
              className="mx-auto max-h-[280px] rounded-md object-contain"
            />
            <button
              type="button"
              className="text-muted-foreground hover:text-foreground absolute right-5 top-5 rounded-full bg-background/80 p-1 backdrop-blur"
              onClick={(e) => {
                e.stopPropagation();
                clearFile();
              }}
            >
              ✕
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 py-8">
            <Upload className="text-muted-foreground size-8" />
            <p className="text-sm font-medium">
              点击或拖拽上传{subjectLabel}图片
            </p>
            <p className="text-muted-foreground text-xs">
              支持 JPG / PNG / WebP
            </p>
          </div>
        )}
      </div>

      {/* 标题输入 */}
      {file && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <FileImage className="text-muted-foreground size-4" />
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="试卷标题（可选）"
              className="h-9"
            />
          </div>
          <div className="flex gap-2">
            <Button
              onClick={() => void handleSubmit()}
              disabled={!file || uploading}
              className="flex-1"
            >
              {uploading ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  上传中...
                </>
              ) : (
                "开始解析"
              )}
            </Button>
            <Button variant="outline" onClick={clearFile} disabled={uploading}>
              取消
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
