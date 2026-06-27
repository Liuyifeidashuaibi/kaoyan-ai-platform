"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  FileUp,
  LayoutTemplate,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";

import {
  createAgentTemplate,
  deleteAgentTemplate,
  ingestTemplateFile,
  listAgentTemplates,
  updateAgentTemplate,
  type AgentTemplate,
} from "@/lib/api/agent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";

const DOC_TYPES = ["pdf", "docx", "xlsx", "pptx"] as const;

/** 默认校验规则 JSON（引导用户填写） */
const DEFAULT_VALIDATION_RULES = `{
  "required_sections": ["摘要", "引言", "结论"],
  "min_chars": 0,
  "max_chars": 0,
  "required_keywords": [],
  "required_heading_levels": [2],
  "custom_checks": []
}`;

const DEFAULT_STYLE_RULES = `{
  "font": "宋体",
  "body_size": "小四",
  "heading_size": "三号黑体",
  "line_spacing": 1.5
}`;

type EditState = {
  id: number | null; // null = 新建
  name: string;
  category: string;
  doc_type: string;
  description: string;
  style_rules: string;
  validation_rules: string;
  source_text: string;
};

const EMPTY_EDIT: EditState = {
  id: null,
  name: "",
  category: "general",
  doc_type: "pdf",
  description: "",
  style_rules: DEFAULT_STYLE_RULES,
  validation_rules: DEFAULT_VALIDATION_RULES,
  source_text: "",
};

function tryParseJSON(text: string): { ok: boolean; value?: unknown; error?: string } {
  if (!text.trim()) return { ok: true, value: {} };
  try {
    return { ok: true, value: JSON.parse(text) };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "JSON 解析失败" };
  }
}

export function AgentTemplatesClient() {
  const [templates, setTemplates] = useState<AgentTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<EditState | null>(null);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // 文件入库
  const [ingestOpen, setIngestOpen] = useState(false);
  const [ingestName, setIngestName] = useState("");
  const [ingestCategory, setIngestCategory] = useState("general");
  const [ingestDocType, setIngestDocType] = useState("pdf");
  const [ingestFile, setIngestFile] = useState<File | null>(null);
  const [ingesting, setIngesting] = useState(false);
  const [ingestError, setIngestError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listAgentTemplates({ active_only: false });
      setTemplates(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载模板失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const openNew = () => {
    setFormError(null);
    setEditing({ ...EMPTY_EDIT });
  };

  const openEdit = (tpl: AgentTemplate) => {
    setFormError(null);
    setEditing({
      id: tpl.id,
      name: tpl.name,
      category: tpl.category,
      doc_type: tpl.doc_type,
      description: tpl.description,
      style_rules: tpl.style_rules || DEFAULT_STYLE_RULES,
      validation_rules: tpl.validation_rules || DEFAULT_VALIDATION_RULES,
      source_text: tpl.source_text || "",
    });
  };

  const handleSave = async () => {
    if (!editing) return;
    if (!editing.name.trim()) {
      setFormError("请填写模板名称");
      return;
    }
    const styleCheck = tryParseJSON(editing.style_rules);
    if (!styleCheck.ok) {
      setFormError(`样式规则 JSON 无效: ${styleCheck.error}`);
      return;
    }
    const validationCheck = tryParseJSON(editing.validation_rules);
    if (!validationCheck.ok) {
      setFormError(`校验规则 JSON 无效: ${validationCheck.error}`);
      return;
    }

    setSaving(true);
    setFormError(null);
    try {
      const payload = {
        name: editing.name.trim(),
        category: editing.category.trim() || "general",
        doc_type: editing.doc_type,
        description: editing.description,
        style_rules: styleCheck.value as Record<string, unknown>,
        validation_rules: validationCheck.value as Record<string, unknown>,
        source_text: editing.source_text,
      };
      if (editing.id === null) {
        await createAgentTemplate(payload);
      } else {
        await updateAgentTemplate(editing.id, payload);
      }
      setEditing(null);
      await load();
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("确定删除该模板？")) return;
    try {
      await deleteAgentTemplate(id);
      setTemplates((prev) => prev.filter((t) => t.id !== id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "删除失败");
    }
  };

  const handleIngestSubmit = async () => {
    if (!ingestFile) {
      setIngestError("请选择模板文件");
      return;
    }
    if (!ingestName.trim()) {
      setIngestError("请填写模板名称");
      return;
    }
    setIngesting(true);
    setIngestError(null);
    try {
      await ingestTemplateFile(
        ingestFile,
        ingestName.trim(),
        ingestCategory.trim() || "general",
        ingestDocType
      );
      setIngestOpen(false);
      setIngestName("");
      setIngestFile(null);
      setIngestCategory("general");
      setIngestDocType("pdf");
      await load();
    } catch (e) {
      setIngestError(e instanceof Error ? e.message : "入库失败");
    } finally {
      setIngesting(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-5 p-4 md:p-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Link href="/agent" className="hover:text-foreground">
              Agent 工作台
            </Link>
            <span>/</span>
            <span>模板管理</span>
          </div>
          <h1 className="mt-1 flex items-center gap-2 text-xl font-semibold tracking-tight">
            <LayoutTemplate className="size-5" />
            模板管理
          </h1>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={load} disabled={loading}>
            <RefreshCw className="size-4" />
            刷新
          </Button>
          <Button variant="outline" size="sm" onClick={() => setIngestOpen(true)}>
            <FileUp className="size-4" />
            文件入库
          </Button>
          <Button size="sm" onClick={openNew}>
            <Plus className="size-4" />
            新建模板
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <AlertCircle className="size-4" />
          {error}
        </div>
      )}

      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : templates.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center gap-2 py-12 text-center">
            <LayoutTemplate className="size-8 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">暂无模板</p>
            <Button size="sm" variant="outline" className="mt-2" onClick={openNew}>
              <Plus className="size-4" />
              创建第一个模板
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {templates.map((tpl) => (
            <Card key={tpl.id}>
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <CardTitle className="truncate text-sm">
                        {tpl.name}
                      </CardTitle>
                      <Badge variant="outline">{tpl.doc_type.toUpperCase()}</Badge>
                      {!tpl.is_active && <Badge variant="secondary">停用</Badge>}
                    </div>
                    {tpl.description && (
                      <p className="mt-1 text-xs text-muted-foreground line-clamp-2">
                        {tpl.description}
                      </p>
                    )}
                    <p className="mt-1 text-xs text-muted-foreground/70">
                      分类：{tpl.category}
                    </p>
                  </div>
                  <div className="flex shrink-0 gap-1">
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      onClick={() => openEdit(tpl)}
                      aria-label="编辑"
                    >
                      <Pencil className="size-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      onClick={() => handleDelete(tpl.id)}
                      aria-label="删除"
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
            </Card>
          ))}
        </div>
      )}

      {/* 新建/编辑弹窗 */}
      <Dialog open={!!editing} onOpenChange={(open) => !open && setEditing(null)}>
        <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editing?.id ? "编辑模板" : "新建模板"}</DialogTitle>
          </DialogHeader>
          {editing && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label htmlFor="tpl-name">名称</Label>
                  <Input
                    id="tpl-name"
                    value={editing.name}
                    onChange={(e) =>
                      setEditing({ ...editing, name: e.target.value })
                    }
                    placeholder="如：学术论文模板"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="tpl-doc-type">文档类型</Label>
                  <select
                    id="tpl-doc-type"
                    value={editing.doc_type}
                    onChange={(e) =>
                      setEditing({ ...editing, doc_type: e.target.value })
                    }
                    className="h-8 w-full rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
                  >
                    {DOC_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t.toUpperCase()}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label htmlFor="tpl-category">分类</Label>
                  <Input
                    id="tpl-category"
                    value={editing.category}
                    onChange={(e) =>
                      setEditing({ ...editing, category: e.target.value })
                    }
                    placeholder="论文 / 报告 / 标书…"
                  />
                </div>
              </div>
              <div className="space-y-1">
                <Label htmlFor="tpl-desc">描述</Label>
                <Textarea
                  id="tpl-desc"
                  value={editing.description}
                  onChange={(e) =>
                    setEditing({ ...editing, description: e.target.value })
                  }
                  rows={2}
                  placeholder="模板用途说明"
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="tpl-style">样式规则（JSON）</Label>
                <Textarea
                  id="tpl-style"
                  value={editing.style_rules}
                  onChange={(e) =>
                    setEditing({ ...editing, style_rules: e.target.value })
                  }
                  rows={5}
                  className="font-mono text-xs"
                  spellCheck={false}
                />
                <p className="text-xs text-muted-foreground">
                  字体 / 字号 / 行距 / 标题层级
                </p>
              </div>
              <div className="space-y-1">
                <Label htmlFor="tpl-validation">校验规则（JSON）</Label>
                <Textarea
                  id="tpl-validation"
                  value={editing.validation_rules}
                  onChange={(e) =>
                    setEditing({ ...editing, validation_rules: e.target.value })
                  }
                  rows={7}
                  className="font-mono text-xs"
                  spellCheck={false}
                />
                <p className="text-xs text-muted-foreground">
                  required_sections / min_chars / required_keywords /
                  required_heading_levels / custom_checks
                </p>
              </div>
              <div className="space-y-1">
                <Label htmlFor="tpl-source">模板原文（可选，向量化用）</Label>
                <Textarea
                  id="tpl-source"
                  value={editing.source_text}
                  onChange={(e) =>
                    setEditing({ ...editing, source_text: e.target.value })
                  }
                  rows={4}
                  placeholder="粘贴模板正文，用于语义检索匹配"
                />
              </div>

              {formError && (
                <div className="flex items-center gap-2 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  <AlertCircle className="size-4" />
                  {formError}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <Button
                  variant="outline"
                  onClick={() => setEditing(null)}
                  disabled={saving}
                >
                  取消
                </Button>
                <Button onClick={handleSave} disabled={saving}>
                  {saving && <Loader2 className="size-4 animate-spin" />}
                  保存
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* 文件入库弹窗 */}
      <Dialog
        open={ingestOpen}
        onOpenChange={(open) => !open && setIngestOpen(false)}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>上传模板文件入库</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <Label htmlFor="ingest-name">名称</Label>
              <Input
                id="ingest-name"
                value={ingestName}
                onChange={(e) => setIngestName(e.target.value)}
                placeholder="如：行业报告模板"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="ingest-category">分类</Label>
                <Input
                  id="ingest-category"
                  value={ingestCategory}
                  onChange={(e) => setIngestCategory(e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="ingest-doc-type">文档类型</Label>
                <select
                  id="ingest-doc-type"
                  value={ingestDocType}
                  onChange={(e) => setIngestDocType(e.target.value)}
                  className="h-8 w-full rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
                >
                  {DOC_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t.toUpperCase()}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="space-y-1">
              <Label>文件（docx/pdf/txt/md）</Label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".docx,.pdf,.txt,.md,.markdown"
                onChange={(e) => setIngestFile(e.target.files?.[0] ?? null)}
                className="block w-full text-sm text-muted-foreground file:mr-3 file:rounded-md file:border-0 file:bg-primary file:px-3 file:py-1.5 file:text-primary-foreground hover:file:bg-primary/90"
              />
              {ingestFile && (
                <p className="text-xs text-muted-foreground">
                  已选: {ingestFile.name}（{(ingestFile.size / 1024).toFixed(1)} KB）
                </p>
              )}
            </div>

            {ingestError && (
              <div className="flex items-center gap-2 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
                <AlertCircle className="size-4" />
                {ingestError}
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="outline"
                onClick={() => setIngestOpen(false)}
                disabled={ingesting}
              >
                取消
              </Button>
              <Button onClick={handleIngestSubmit} disabled={ingesting}>
                {ingesting && <Loader2 className="size-4 animate-spin" />}
                入库
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
