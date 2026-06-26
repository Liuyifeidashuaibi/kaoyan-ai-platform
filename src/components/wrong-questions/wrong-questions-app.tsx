"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ChevronLeft,
  FolderPlus,
  Plus,
  Upload,
} from "lucide-react";

import { CategoryFolderCard } from "@/components/wrong-questions/category-folder-card";
import { ImageViewer, buildSlides } from "@/components/wrong-questions/image-viewer";
import { MaterialTimelineItem } from "@/components/wrong-questions/question-card";
import { QuestionDetailDialog } from "@/components/wrong-questions/question-detail-dialog";
import { UploadDialog } from "@/components/wrong-questions/upload-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  analyzeWrongQuestion,
  createCategory,
  listCategories,
  listWrongQuestions,
  updateWrongQuestion,
  uploadWrongQuestion,
} from "@/lib/api/wrong-questions";
import type {
  MaterialFileType,
  WrongQuestion,
  WrongQuestionCategory,
} from "@/lib/api/types";
import { MATERIAL_TYPE_FILTERS } from "@/lib/wrong-questions/material-utils";
import { cn } from "@/lib/utils";

type WrongQuestionsAppProps = {
  initialFolder?: string;
};

export function WrongQuestionsApp({ initialFolder }: WrongQuestionsAppProps = {}) {
  const router = useRouter();
  const openedFromUrl = useRef(false);
  const [categories, setCategories] = useState<WrongQuestionCategory[]>([]);
  const [questions, setQuestions] = useState<WrongQuestion[]>([]);
  const [activeCategory, setActiveCategory] =
    useState<WrongQuestionCategory | null>(null);
  const [typeFilter, setTypeFilter] = useState<MaterialFileType | "all">("all");
  const [selectedQuestion, setSelectedQuestion] = useState<WrongQuestion | null>(
    null
  );
  const [uploadOpen, setUploadOpen] = useState(false);
  const [viewerOpen, setViewerOpen] = useState(false);
  const [viewerIndex, setViewerIndex] = useState(0);
  const [folderDialogOpen, setFolderDialogOpen] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadCategories = useCallback(async () => {
    const cats = await listCategories();
    setCategories(cats);
    return cats;
  }, []);

  const refreshCategories = useCallback(async () => {
    setLoading(true);
    try {
      await loadCategories();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [loadCategories]);

  useEffect(() => {
    void refreshCategories();
  }, [refreshCategories]);

  const openCategory = useCallback(async (category: WrongQuestionCategory) => {
    setTypeFilter("all");
    setActiveCategory(category);
  }, []);

  useEffect(() => {
    if (!initialFolder || openedFromUrl.current || loading) return;

    const openByName = async () => {
      const cats = categories.length > 0 ? categories : await loadCategories();
      const existing = cats.find((c) => c.name === initialFolder);
      if (existing) {
        await openCategory(existing);
        openedFromUrl.current = true;
      }
    };

    void openByName();
  }, [initialFolder, categories, loading, loadCategories, openCategory]);

  const activeCategoryId = activeCategory?.id ?? null;

  useEffect(() => {
    if (activeCategoryId == null) {
      setQuestions([]);
      return;
    }

    let cancelled = false;
    setLoading(true);

    (async () => {
      try {
        const fileType = typeFilter === "all" ? null : typeFilter;
        const qs = await listWrongQuestions(activeCategoryId, fileType);
        if (!cancelled) setQuestions(qs);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to load materials");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [activeCategoryId, typeFilter]);

  const backToFolders = () => {
    setActiveCategory(null);
    setTypeFilter("all");
    openedFromUrl.current = false;
    router.replace("/wrong-questions");
    void refreshCategories();
  };

  const handleUpload = async (params: {
    file: File;
    categoryId?: number;
    categoryName?: string;
    title: string;
    notes: string;
  }) => {
    const created = await uploadWrongQuestion(params);
    const cats = await loadCategories();
    const targetId = params.categoryId ?? created.category_id;
    const folder = cats.find((c) => c.id === targetId) ?? null;
    if (folder) {
      setActiveCategory(folder);
    }
  };

  const handleCreateFolder = async () => {
    const name = newFolderName.trim();
    if (!name) return;
    try {
      const cat = await createCategory(name);
      setNewFolderName("");
      setFolderDialogOpen(false);
      setActiveCategory({
        ...cat,
        question_count: cat.question_count ?? 0,
      });
      await loadCategories();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create folder");
    }
  };

  const handleAnalyze = async (id: number) => {
    setAnalyzing(true);
    try {
      const { ai_analysis } = await analyzeWrongQuestion(id);
      setQuestions((prev) =>
        prev.map((q) => (q.id === id ? { ...q, ai_analysis } : q))
      );
      if (selectedQuestion?.id === id) {
        setSelectedQuestion((prev) =>
          prev ? { ...prev, ai_analysis } : prev
        );
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "AI analysis failed");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleUpdateNotes = async (id: number, notes: string) => {
    const updated = await updateWrongQuestion(id, { notes });
    setQuestions((prev) =>
      prev.map((q) => (q.id === id ? updated : q))
    );
    if (selectedQuestion?.id === id) {
      setSelectedQuestion(updated);
    }
  };

  const imageQuestions = questions.filter((q) => q.file_type === "image");
  const inFolder = activeCategory !== null;

  return (
    <div className="flex min-h-[calc(100vh-3.5rem)] flex-col">
      <div className="border-b border-border px-4 py-4 md:px-6">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            {inFolder && (
              <Button variant="ghost" size="icon-sm" onClick={backToFolders}>
                <ChevronLeft className="size-4" />
              </Button>
            )}
            <h1 className="text-lg font-semibold">
              {inFolder ? activeCategory.name : "Notebook"}
            </h1>
          </div>
          <div className="flex gap-2">
            {inFolder ? (
              <Button size="sm" onClick={() => setUploadOpen(true)}>
                <Upload className="size-4" />
                Add Material
              </Button>
            ) : (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setFolderDialogOpen(true)}
                >
                  <FolderPlus className="size-4" />
                  New Subject
                </Button>
                <Button
                  size="sm"
                  onClick={() => setUploadOpen(true)}
                  disabled={categories.length === 0}
                >
                  <Plus className="size-4" />
                  Upload
                </Button>
              </>
            )}
          </div>
        </div>
      </div>

      {error && (
        <div className="border-b border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive md:px-6">
          {error}
          <button
            type="button"
            className="ml-2 underline"
            onClick={() => setError(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="flex-1 px-4 py-6 md:px-6">
        <div className="mx-auto max-w-6xl">
          {loading ? (
            <p className="py-20 text-center text-sm text-muted-foreground">
              Loading...
            </p>
          ) : !inFolder ? (
            categories.length === 0 ? (
              <div className="flex flex-col items-center py-20 text-center">
                <div className="mb-4 flex size-12 items-center justify-center rounded-full border border-border">
                  <Plus className="size-5 text-muted-foreground" />
                </div>
                <p className="text-sm text-muted-foreground">No subject folders yet</p>
                <Button
                  variant="outline"
                  className="mt-6"
                  onClick={() => setFolderDialogOpen(true)}
                >
                  Create your first subject folder
                </Button>
              </div>
            ) : (
              <div className="overflow-hidden rounded-xl border border-border/50">
                {categories.map((cat) => (
                  <CategoryFolderCard
                    key={cat.id}
                    category={cat}
                    onClick={() => void openCategory(cat)}
                  />
                ))}
              </div>
            )
          ) : (
            <>
              <div className="mb-6 flex flex-wrap gap-2">
                {MATERIAL_TYPE_FILTERS.map((item) => (
                  <button
                    key={item.value}
                    type="button"
                    onClick={() => setTypeFilter(item.value)}
                    className={cn(
                      "rounded-full border px-3 py-1 text-sm transition-colors",
                      typeFilter === item.value
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border bg-background text-muted-foreground hover:bg-muted"
                    )}
                  >
                    {item.label}
                  </button>
                ))}
              </div>

              {questions.length === 0 ? (
                <div className="flex flex-col items-center py-20 text-center">
                  <p className="text-muted-foreground">
                    {typeFilter === "all"
                      ? `No materials in "${activeCategory.name}" yet`
                      : `No ${MATERIAL_TYPE_FILTERS.find((f) => f.value === typeFilter)?.label ?? ""} materials in "${activeCategory.name}"`}
                  </p>
                  <Button className="mt-4" onClick={() => setUploadOpen(true)}>
                    Add first material
                  </Button>
                </div>
              ) : (
                <div className="max-w-3xl">
                  {questions.map((q, idx) => (
                    <MaterialTimelineItem
                      key={q.id}
                      question={q}
                      isLast={idx === questions.length - 1}
                      onClick={() => setSelectedQuestion(q)}
                      onPreviewClick={(e) => {
                        if (q.file_type !== "image") return;
                        e.stopPropagation();
                        const imageIdx = imageQuestions.findIndex(
                          (item) => item.id === q.id
                        );
                        if (imageIdx >= 0) {
                          setViewerIndex(imageIdx);
                          setViewerOpen(true);
                        }
                      }}
                    />
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <ImageViewer
        open={viewerOpen}
        index={viewerIndex}
        slides={buildSlides(imageQuestions)}
        onClose={() => setViewerOpen(false)}
      />

      <UploadDialog
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        categories={categories}
        lockedCategory={inFolder ? activeCategory : null}
        onUpload={handleUpload}
      />

      <QuestionDetailDialog
        question={selectedQuestion}
        open={!!selectedQuestion}
        onOpenChange={(open) => {
          if (!open) setSelectedQuestion(null);
        }}
        onAnalyze={handleAnalyze}
        onUpdateNotes={handleUpdateNotes}
        analyzing={analyzing}
      />

      <Dialog open={folderDialogOpen} onOpenChange={setFolderDialogOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>New Subject Folder</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="folder-name">Subject name</Label>
            <Input
              id="folder-name"
              placeholder="e.g. Math, English, Politics"
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleCreateFolder();
              }}
            />
          </div>
          <DialogFooter>
            <Button
              onClick={() => void handleCreateFolder()}
              disabled={!newFolderName.trim()}
            >
              Create & Open
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
