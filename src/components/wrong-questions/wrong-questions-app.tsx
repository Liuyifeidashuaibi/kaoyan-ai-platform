"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ChevronLeft, FolderPlus, ImagePlus, Plus } from "lucide-react";

import { CategoryFolderCard } from "@/components/wrong-questions/category-folder-card";
import { ImageViewer, buildSlides } from "@/components/wrong-questions/image-viewer";
import { QuestionCard } from "@/components/wrong-questions/question-card";
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
  startChatFromQuestion,
  updateWrongQuestion,
  uploadWrongQuestion,
} from "@/lib/api/wrong-questions";
import type { WrongQuestion, WrongQuestionCategory } from "@/lib/api/types";

export function WrongQuestionsApp() {
  const [categories, setCategories] = useState<WrongQuestionCategory[]>([]);
  const [questions, setQuestions] = useState<WrongQuestion[]>([]);
  const [activeCategory, setActiveCategory] =
    useState<WrongQuestionCategory | null>(null);
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
  const [startingChat, setStartingChat] = useState(false);
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
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [loadCategories]);

  useEffect(() => {
    void refreshCategories();
  }, [refreshCategories]);

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
        const qs = await listWrongQuestions(activeCategoryId);
        if (!cancelled) setQuestions(qs);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "加载错题失败");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [activeCategoryId]);

  const openCategory = (category: WrongQuestionCategory) => {
    setActiveCategory(category);
  };

  const backToFolders = () => {
    setActiveCategory(null);
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
      setError(e instanceof Error ? e.message : "创建文件夹失败");
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
      setError(e instanceof Error ? e.message : "AI 解析失败");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleStartChat = async (id: number): Promise<string> => {
    setStartingChat(true);
    try {
      const result = await startChatFromQuestion(id);
      return result.session_id;
    } finally {
      setStartingChat(false);
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

  const inFolder = activeCategory !== null;

  return (
    <div className="flex min-h-[calc(100vh-3.5rem)] flex-col">
      <div className="border-b border-border px-4 py-4 md:px-6">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            {inFolder ? (
              <Button variant="ghost" size="icon-sm" onClick={backToFolders}>
                <ChevronLeft className="size-4" />
              </Button>
            ) : (
              <Link href="/">
                <Button variant="ghost" size="icon-sm">
                  <ArrowLeft className="size-4" />
                </Button>
              </Link>
            )}
            <div>
              <h1 className="text-lg font-semibold">
                {inFolder ? activeCategory.name : "错题本"}
              </h1>
              <p className="text-sm text-muted-foreground">
                {inFolder
                  ? `${questions.length} 道错题 · 点击图片查看介绍与 AI 解析`
                  : "按科目分文件夹整理，上传图片并记录介绍"}
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            {inFolder ? (
              <Button size="sm" onClick={() => setUploadOpen(true)}>
                <ImagePlus className="size-4" />
                添加图片
              </Button>
            ) : (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setFolderDialogOpen(true)}
                >
                  <FolderPlus className="size-4" />
                  新建科目
                </Button>
                <Button
                  size="sm"
                  onClick={() => setUploadOpen(true)}
                  disabled={categories.length === 0}
                >
                  <Plus className="size-4" />
                  上传错题
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
            关闭
          </button>
        </div>
      )}

      <div className="flex-1 px-4 py-6 md:px-6">
        <div className="mx-auto max-w-6xl">
          {loading ? (
            <p className="py-20 text-center text-sm text-muted-foreground">
              加载中...
            </p>
          ) : !inFolder ? (
            categories.length === 0 ? (
              <div className="flex flex-col items-center py-20 text-center">
                <div className="mb-4 flex size-20 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-600">
                  <FolderPlus className="size-10" />
                </div>
                <p className="text-muted-foreground">还没有科目文件夹</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  先创建「高等数学」「英语」等科目，再往里添加错题图片
                </p>
                <Button
                  className="mt-6"
                  onClick={() => setFolderDialogOpen(true)}
                >
                  创建第一个科目文件夹
                </Button>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
                {categories.map((cat) => (
                  <CategoryFolderCard
                    key={cat.id}
                    category={cat}
                    onClick={() => void openCategory(cat)}
                  />
                ))}
              </div>
            )
          ) : questions.length === 0 ? (
            <div className="flex flex-col items-center py-20 text-center">
              <p className="text-muted-foreground">
                「{activeCategory.name}」里还没有错题
              </p>
              <Button className="mt-4" onClick={() => setUploadOpen(true)}>
                添加第一道错题
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {questions.map((q, idx) => (
                <QuestionCard
                  key={q.id}
                  question={q}
                  onClick={() => setSelectedQuestion(q)}
                  onImageClick={(e) => {
                    e.stopPropagation();
                    setViewerIndex(idx);
                    setViewerOpen(true);
                  }}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      <ImageViewer
        open={viewerOpen}
        index={viewerIndex}
        slides={buildSlides(questions)}
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
        onStartChat={handleStartChat}
        onUpdateNotes={handleUpdateNotes}
        analyzing={analyzing}
        startingChat={startingChat}
      />

      <Dialog open={folderDialogOpen} onOpenChange={setFolderDialogOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>新建科目文件夹</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="folder-name">科目名称</Label>
            <Input
              id="folder-name"
              placeholder="如：高等数学、英语、政治"
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
              创建并打开
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
