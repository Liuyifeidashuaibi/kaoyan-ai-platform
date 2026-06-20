"use client";

import { useCallback, useState } from "react";

import { AdminRecordDialog } from "@/components/admin/schools/admin-record-dialog";
import { UniversityPicker } from "@/components/admin/schools/university-picker";
import { AdminModulePage } from "@/components/admin/layout/admin-module-page";
import {
  AdminDataTableShell,
  AdminTableFooter,
  formatAdminDate,
} from "@/components/admin/data-table/admin-data-table";
import { FilterBar } from "@/components/admin/shared/filter-bar";
import { useAdminToast } from "@/components/admin/shared/admin-toast";
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
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { adminNavItems } from "@/config/admin-navigation";
import { useAdminList } from "@/hooks/use-admin-list";
import {
  createAdminPdf,
  deleteAdminPdf,
  fetchAdminPdfs,
  updateAdminPdf,
  type AdminPdf,
} from "@/lib/admin/api/schools";

const nav = adminNavItems.find((item) => item.id === "schools")!;

function formatBytes(n: number | null) {
  if (!n) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

const EDIT_FIELDS = [
  { key: "file_name", label: "文件名", required: true },
  { key: "file_path", label: "存储路径", required: true },
  { key: "source_url", label: "来源 URL" },
  { key: "file_size", label: "大小（字节）" },
];

export function PdfsListClient() {
  const { toast } = useAdminToast();
  const [editOpen, setEditOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<AdminPdf | null>(null);
  const [schoolId, setSchoolId] = useState("");
  const [createForm, setCreateForm] = useState({
    file_name: "",
    file_path: "",
    source_url: "",
    file_size: "",
  });

  const fetcher = useCallback(
    (p: { page: number; pageSize: number; q: string }) =>
      fetchAdminPdfs({ page: p.page, pageSize: p.pageSize, q: p.q }),
    []
  );

  const { q, setQ, page, setPage, loading, error, items, total, pageSize, search, reload } =
    useAdminList({ fetcher });

  async function handleCreate() {
    if (!createForm.file_name.trim() || !createForm.file_path.trim()) {
      toast("请填写文件名和路径", "error");
      return;
    }
    await createAdminPdf({
      school_id: schoolId || null,
      file_name: createForm.file_name,
      file_path: createForm.file_path,
      file_type: "application/pdf",
      source_url: createForm.source_url || null,
      file_size: createForm.file_size ? Number(createForm.file_size) : null,
    });
    toast("PDF 记录已创建", "success");
    setCreateOpen(false);
    await reload();
  }

  async function handleDelete(id: string) {
    if (!window.confirm("确定删除该 PDF 记录？")) return;
    try {
      await deleteAdminPdf(id);
      toast("已删除", "success");
      await reload();
    } catch (e) {
      toast(e instanceof Error ? e.message : "删除失败", "error");
    }
  }

  return (
    <AdminModulePage
      title="PDF 管理"
      subNav={nav.children}
      actions={
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          登记 PDF
        </Button>
      }
    >
      <FilterBar value={q} onChange={setQ} onSearch={search} placeholder="搜索文件名" />
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <AdminDataTableShell>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>文件名</TableHead>
              <TableHead>大小</TableHead>
              <TableHead>路径</TableHead>
              <TableHead>入库时间</TableHead>
              <TableHead className="text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell colSpan={5}>
                      <Skeleton className="h-8 w-full" />
                    </TableCell>
                  </TableRow>
                ))
              : items.map((f) => (
                  <TableRow key={f.id}>
                    <TableCell className="max-w-xs truncate font-medium">{f.file_name}</TableCell>
                    <TableCell className="text-muted-foreground">{formatBytes(f.file_size)}</TableCell>
                    <TableCell className="max-w-xs truncate font-mono text-xs text-muted-foreground">
                      {f.file_path}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatAdminDate(f.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setEditing(f);
                          setEditOpen(true);
                        }}
                      >
                        编辑
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive"
                        onClick={() => void handleDelete(f.id)}
                      >
                        删除
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
          </TableBody>
        </Table>
        <AdminTableFooter total={total} page={page} pageSize={pageSize} onPageChange={setPage} />
      </AdminDataTableShell>

      <AdminRecordDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        title="编辑 PDF 记录"
        fields={EDIT_FIELDS}
        initial={
          editing
            ? {
                file_name: editing.file_name,
                file_path: editing.file_path,
                source_url: editing.source_url ?? "",
                file_size: editing.file_size ? String(editing.file_size) : "",
              }
            : undefined
        }
        onSubmit={async (values) => {
          if (!editing) return;
          await updateAdminPdf(editing.id, {
            file_name: values.file_name,
            file_path: values.file_path,
            source_url: values.source_url || null,
            file_size: values.file_size ? Number(values.file_size) : null,
          });
          toast("已更新", "success");
          await reload();
        }}
      />

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>登记 PDF</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <UniversityPicker value={schoolId} onChange={setSchoolId} label="关联院校（可选）" />
            {EDIT_FIELDS.map((field) => (
              <div key={field.key} className="grid gap-2">
                <Label>{field.label}</Label>
                <Input
                  value={createForm[field.key as keyof typeof createForm]}
                  placeholder={
                    "placeholder" in field
                      ? (field as { placeholder?: string }).placeholder
                      : undefined
                  }
                  onChange={(e) =>
                    setCreateForm((prev) => ({ ...prev, [field.key]: e.target.value }))
                  }
                />
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              取消
            </Button>
            <Button onClick={() => void handleCreate()}>保存</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AdminModulePage>
  );
}
