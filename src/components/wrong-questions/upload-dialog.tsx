"use client";

import { useEffect, useRef, useState } from "react";
import {
  FileAudio,
  FileText,
  FileVideo,
  ImagePlus,
  Upload,
} from "lucide-react";

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
import type { MaterialFileType, WrongQuestionCategory } from "@/lib/api/types";
import {
  MATERIAL_TYPE_LABELS,
  UPLOAD_ACCEPT,
} from "@/lib/wrong-questions/material-utils";

type UploadDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  categories: WrongQuestionCategory[];
  lockedCategory?: WrongQuestionCategory | null;
  onUpload: (params: {
    file: File;
    categoryId?: number;
    categoryName?: string;
    title: string;
    notes: string;
  }) => Promise<void>;
};

function detectClientFileType(file: File): MaterialFileType {
  if (file.type.startsWith("image/")) return "image";
  if (file.type.startsWith("video/")) return "video";
  if (file.type.startsWith("audio/")) return "audio";
  const ext = file.name.split(".").pop()?.toLowerCase() || "";
  if (["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "md", "csv"].includes(ext)) {
    return "document";
  }
  return "other";
}

function FilePreview({
  file,
  preview,
  fileType,
}: {
  file: File;
  preview: string | null;
  fileType: MaterialFileType;
}) {
  if (fileType === "image" && preview) {
    return (
      /* eslint-disable-next-line @next/next/no-img-element */
      <img
        src={preview}
        alt="Preview"
        className="max-h-44 w-full rounded-lg border object-contain"
      />
    );
  }

  if (fileType === "video" && preview) {
    return (
      <video
        src={preview}
        controls
        className="max-h-44 w-full rounded-lg border bg-black object-contain"
      />
    );
  }

  const Icon =
    fileType === "video"
      ? FileVideo
      : fileType === "audio"
        ? FileAudio
        : fileType === "document"
          ? FileText
          : Upload;

  return (
    <div className="flex h-36 w-full flex-col items-center justify-center gap-2 rounded-lg border bg-muted/40 px-4 text-center">
      <Icon className="size-10 text-muted-foreground" />
      <p className="truncate text-sm font-medium">{file.name}</p>
      <p className="text-xs text-muted-foreground">
        {MATERIAL_TYPE_LABELS[fileType]} · {(file.size / 1024 / 1024).toFixed(2)} MB
      </p>
    </div>
  );
}

export function UploadDialog({
  open,
  onOpenChange,
  categories,
  lockedCategory,
  onUpload,
}: UploadDialogProps) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [fileType, setFileType] = useState<MaterialFileType>("image");
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
    setFileType("image");
    setTitle("");
    setNotes("");
    setCategoryId("");
    setNewCategory("");
    setUseNewCategory(categories.length === 0);
    setError(null);
  };

  const handleFile = (f: File) => {
    const type = detectClientFileType(f);
    setFile(f);
    setFileType(type);
    if (preview) URL.revokeObjectURL(preview);
    if (type === "image" || type === "video") {
      setPreview(URL.createObjectURL(f));
    } else {
      setPreview(null);
    }
    if (!title.trim()) {
      setTitle(f.name.replace(/\.[^.]+$/, "") || "Untitled");
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
      setError("Select or create a subject folder");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await onUpload({
        file,
        categoryId: resolvedCategoryId,
        categoryName: resolvedCategoryName,
        title: title.trim() || "Untitled",
        notes,
      });
      reset();
      onOpenChange(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed. Try again.");
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
              ? `Upload to "${lockedCategory.name}"`
              : "Upload Material"}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <input
              ref={fileRef}
              type="file"
              accept={UPLOAD_ACCEPT}
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleFile(f);
              }}
            />
            {file ? (
              <button
                type="button"
                className="block w-full"
                onClick={() => fileRef.current?.click()}
              >
                <FilePreview file={file} preview={preview} fileType={fileType} />
              </button>
            ) : (
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                className="flex h-36 w-full flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border text-muted-foreground hover:bg-muted/50"
              >
                <ImagePlus className="size-8" />
                <span className="text-sm">Choose image, video, document, or audio</span>
                <span className="text-xs text-muted-foreground">
                  PDF, Word, PPT, MP4, MP3, and other common formats
                </span>
              </button>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="wq-title">Title</Label>
            <Input
              id="wq-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Calculus problem 3, English listening Unit 5"
            />
          </div>

          {!lockedCategory && (
            <div className="space-y-2">
              <Label>Subject folder</Label>
              {!useNewCategory ? (
                <select
                  value={categoryId}
                  onChange={(e) => setCategoryId(e.target.value)}
                  className="h-9 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm"
                >
                  <option value="">Select subject…</option>
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              ) : (
                <Input
                  placeholder="New subject, e.g. Math, English"
                  value={newCategory}
                  onChange={(e) => setNewCategory(e.target.value)}
                />
              )}
              <button
                type="button"
                className="text-xs text-primary underline"
                onClick={() => setUseNewCategory(!useNewCategory)}
              >
                {useNewCategory ? "Choose existing subject" : "Create new subject folder"}
              </button>
            </div>
          )}

          {lockedCategory && (
            <p className="text-sm text-muted-foreground">
              Saving to subject:
              <span className="font-medium text-foreground">
                {lockedCategory.name}
              </span>
            </p>
          )}

          <div className="space-y-2">
            <Label htmlFor="wq-notes">Notes</Label>
            <Textarea
              id="wq-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Key points, common mistakes, solution ideas…"
              rows={4}
            />
          </div>

          {error ? <p className="text-sm text-destructive">{error}</p> : null}
        </div>

        <DialogFooter>
          <Button onClick={handleSubmit} disabled={submitting || !canSubmit}>
            {submitting ? "Uploading…" : "Save to Notebook"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
