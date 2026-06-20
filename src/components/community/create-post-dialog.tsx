"use client";

import { useEffect, useState } from "react";
import { Loader2, Paperclip, Plus } from "lucide-react";

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
import { createPost, uploadCommunityAttachment } from "@/lib/api/community";
import type { CommunityAttachment } from "@/lib/api/types";
import { prefetchUniversitiesList } from "@/lib/api/schools";
import {
  COHORT_GRADES,
  POST_TYPES,
  SUBJECT_CATEGORIES,
  type PostType,
} from "@/lib/community/constants";

type CreatePostDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultSubjectCategory?: string;
  onCreated?: () => void;
};

export function CreatePostDialog({
  open,
  onOpenChange,
  defaultSubjectCategory,
  onCreated,
}: CreatePostDialogProps) {
  const [postType, setPostType] = useState<PostType>("experience");
  const [subjectCategory, setSubjectCategory] = useState(
    defaultSubjectCategory || SUBJECT_CATEGORIES[7]
  );
  const [grade, setGrade] = useState<string>(COHORT_GRADES[3]);
  const [universityId, setUniversityId] = useState("");
  const [schools, setSchools] = useState<{ id: string; name: string }[]>([]);
  const [schoolsLoading, setSchoolsLoading] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [attachments, setAttachments] = useState<CommunityAttachment[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setSchoolsLoading(true);
    prefetchUniversitiesList()
      .then((list) => {
        if (!cancelled) {
          setSchools(list.map((u) => ({ id: u.id, name: u.name })));
        }
      })
      .catch(() => {
        if (!cancelled) setSchools([]);
      })
      .finally(() => {
        if (!cancelled) setSchoolsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  async function handleUpload(file: File) {
    setUploading(true);
    setError(null);
    try {
      const item = await uploadCommunityAttachment(file);
      setAttachments((prev) => [...prev, item]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleSubmit() {
    if (!title.trim()) {
      setError("Title is required");
      return;
    }
    if (!grade) {
      setError("Please select a cohort");
      return;
    }
    if (!subjectCategory) {
      setError("Please select a subject area");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const selectedSchool = schools.find((s) => s.id === universityId);
      await createPost({
        post_type: postType,
        subject_category: subjectCategory,
        grade,
        university_id: universityId || null,
        university_name: selectedSchool?.name ?? null,
        title: title.trim(),
        content,
        attachments,
      });
      setTitle("");
      setContent("");
      setAttachments([]);
      setUniversityId("");
      onOpenChange(false);
      onCreated?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to publish");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>New Post</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Post type</Label>
            <div className="flex gap-2">
              {POST_TYPES.map((t) => (
                <Button
                  key={t.value}
                  type="button"
                  size="sm"
                  variant={postType === t.value ? "default" : "outline"}
                  onClick={() => setPostType(t.value)}
                >
                  {t.label}
                </Button>
              ))}
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="subject">
                Subject area <span className="text-destructive">*</span>
              </Label>
              <select
                id="subject"
                required
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                value={subjectCategory}
                onChange={(e) => setSubjectCategory(e.target.value)}
              >
                {SUBJECT_CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="grade">
                Cohort <span className="text-destructive">*</span>
              </Label>
              <select
                id="grade"
                required
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                value={grade}
                onChange={(e) => setGrade(e.target.value)}
              >
                {COHORT_GRADES.map((g) => (
                  <option key={g} value={g}>
                    {g}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="school">School (optional)</Label>
            <select
              id="school"
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
              value={universityId}
              onChange={(e) => setUniversityId(e.target.value)}
              disabled={schoolsLoading}
            >
              <option value="">No school selected</option>
              {schools.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="title">
              Title <span className="text-destructive">*</span>
            </Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Enter title"
              maxLength={200}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="content">Content</Label>
            <Textarea
              id="content"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Share your experience or describe your resources…"
              rows={6}
            />
          </div>

          <div className="space-y-2">
            <Label>Attachments</Label>
            <div className="flex flex-wrap gap-2">
              <label className="inline-flex cursor-pointer items-center gap-1 rounded-md border px-3 py-1.5 text-sm hover:bg-muted">
                {uploading ? <Loader2 className="size-4 animate-spin" /> : <Paperclip className="size-4" />}
                Add attachment
                <input
                  type="file"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) void handleUpload(f);
                    e.target.value = "";
                  }}
                />
              </label>
            </div>
            {attachments.map((a) => (
              <p key={a.url} className="text-xs text-muted-foreground">
                {a.name}
              </p>
            ))}
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>

        <DialogFooter>
          <Button onClick={handleSubmit} disabled={submitting || uploading}>
            {submitting ? <Loader2 className="animate-spin" /> : <Plus />}
            Publish
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
