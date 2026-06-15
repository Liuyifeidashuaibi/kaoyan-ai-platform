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
      setError(e instanceof Error ? e.message : "上传失败");
    } finally {
      setUploading(false);
    }
  }

  async function handleSubmit() {
    if (!title.trim()) {
      setError("请填写标题");
      return;
    }
    if (!grade) {
      setError("请选择年级");
      return;
    }
    if (!subjectCategory) {
      setError("请选择专业");
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
      setError(e instanceof Error ? e.message : "发布失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>发布帖子</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label>帖子类型</Label>
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
                专业 <span className="text-destructive">*</span>
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
                年级 <span className="text-destructive">*</span>
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
            <Label htmlFor="school">学校（可选）</Label>
            <select
              id="school"
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
              value={universityId}
              onChange={(e) => setUniversityId(e.target.value)}
              disabled={schoolsLoading}
            >
              <option value="">不选择学校</option>
              {schools.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="title">
              标题 <span className="text-destructive">*</span>
            </Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="输入标题"
              maxLength={200}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="content">正文</Label>
            <Textarea
              id="content"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="分享你的经验或资料说明…"
              rows={6}
            />
          </div>

          <div className="space-y-2">
            <Label>附件</Label>
            <div className="flex flex-wrap gap-2">
              <label className="inline-flex cursor-pointer items-center gap-1 rounded-md border px-3 py-1.5 text-sm hover:bg-muted">
                {uploading ? <Loader2 className="size-4 animate-spin" /> : <Paperclip className="size-4" />}
                添加附件
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
            发布
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
