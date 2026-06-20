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
  createAdminMajor,
  fetchAdminMajors,
  updateAdminMajor,
  type AdminMajor,
} from "@/lib/admin/api/schools";

const nav = adminNavItems.find((item) => item.id === "schools")!;

const EDIT_FIELDS = [
  { key: "name", label: "专业名称", required: true },
  { key: "code", label: "代码" },
  { key: "college", label: "学院" },
  { key: "subject_category", label: "学科门类" },
  { key: "degree_type", label: "学位类型", placeholder: "学硕/专硕" },
  { key: "study_mode", label: "学习方式", placeholder: "全日制/非全日制" },
];

export function MajorsListClient() {
  const { toast } = useAdminToast();
  const [editOpen, setEditOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<AdminMajor | null>(null);
  const [universityId, setUniversityId] = useState("");
  const [createForm, setCreateForm] = useState({
    name: "",
    code: "",
    college: "",
    subject_category: "",
    degree_type: "学硕",
    study_mode: "全日制",
  });

  const fetcher = useCallback(
    (p: { page: number; pageSize: number; q: string }) =>
      fetchAdminMajors({ page: p.page, pageSize: p.pageSize, q: p.q }),
    []
  );

  const { q, setQ, page, setPage, loading, error, items, total, pageSize, search, reload } =
    useAdminList({ fetcher });

  async function handleCreate() {
    if (!universityId || !createForm.name.trim()) {
      toast("请选择院校并填写专业名称", "error");
      return;
    }
    await createAdminMajor({
      university_id: universityId,
      name: createForm.name,
      code: createForm.code || null,
      college: createForm.college || null,
      subject_category: createForm.subject_category || null,
      degree_type: createForm.degree_type || null,
      study_mode: createForm.study_mode || null,
    });
    toast("专业已创建", "success");
    setCreateOpen(false);
    await reload();
  }

  return (
    <AdminModulePage
      title="专业管理"
      description="专业目录维护"
      subNav={nav.children}
      actions={
        <Button
          size="sm"
          onClick={() => {
            setUniversityId("");
            setCreateForm({
              name: "",
              code: "",
              college: "",
              subject_category: "",
              degree_type: "学硕",
              study_mode: "全日制",
            });
            setCreateOpen(true);
          }}
        >
          新建专业
        </Button>
      }
    >
      <FilterBar value={q} onChange={setQ} onSearch={search} placeholder="搜索专业名称" />
      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <AdminDataTableShell>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>专业</TableHead>
              <TableHead>代码</TableHead>
              <TableHead>学院</TableHead>
              <TableHead>学位/方式</TableHead>
              <TableHead>更新时间</TableHead>
              <TableHead className="text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell colSpan={6}>
                      <Skeleton className="h-8 w-full" />
                    </TableCell>
                  </TableRow>
                ))
              : items.map((major) => (
                  <TableRow key={major.id}>
                    <TableCell className="font-medium">{major.name}</TableCell>
                    <TableCell className="text-muted-foreground">{major.code || "—"}</TableCell>
                    <TableCell className="text-muted-foreground">{major.college || "—"}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {[major.degree_type, major.study_mode].filter(Boolean).join(" · ") || "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatAdminDate(major.updated_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setEditing(major);
                          setEditOpen(true);
                        }}
                      >
                        编辑
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
        title="编辑专业"
        fields={EDIT_FIELDS}
        initial={
          editing
            ? {
                name: editing.name,
                code: editing.code ?? "",
                college: editing.college ?? "",
                subject_category: editing.subject_category ?? "",
                degree_type: editing.degree_type ?? "",
                study_mode: editing.study_mode ?? "",
              }
            : undefined
        }
        onSubmit={async (values) => {
          if (!editing) return;
          await updateAdminMajor(editing.id, {
            name: values.name,
            code: values.code || null,
            college: values.college || null,
            subject_category: values.subject_category || null,
            degree_type: values.degree_type || null,
            study_mode: values.study_mode || null,
          });
          toast("专业已更新", "success");
          await reload();
        }}
      />

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>新建专业</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <UniversityPicker value={universityId} onChange={setUniversityId} />
            {EDIT_FIELDS.map((field) => (
              <div key={field.key} className="grid gap-2">
                <Label>{field.label}</Label>
                <Input
                  value={createForm[field.key as keyof typeof createForm]}
                  placeholder={field.placeholder}
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
