"use client";

import { useCallback, useState } from "react";

import { AdminRecordDialog } from "@/components/admin/schools/admin-record-dialog";
import { UniversityPicker } from "@/components/admin/schools/university-picker";
import { AdminModulePage } from "@/components/admin/layout/admin-module-page";
import {
  AdminDataTableShell,
  AdminTableFooter,
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
  createAdminAnnouncement,
  deleteAdminAnnouncement,
  fetchAdminAnnouncements,
  updateAdminAnnouncement,
  type AdminAnnouncement,
} from "@/lib/admin/api/schools";

const nav = adminNavItems.find((item) => item.id === "schools")!;

const EDIT_FIELDS = [
  { key: "title", label: "标题", required: true },
  { key: "publish_time", label: "发布日期", placeholder: "YYYY-MM-DD" },
  { key: "url", label: "链接", required: true },
  { key: "type", label: "类型", placeholder: "招生简章/招生公告" },
  { key: "content", label: "摘要" },
];

export function AnnouncementsListClient() {
  const { toast } = useAdminToast();
  const [editOpen, setEditOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<AdminAnnouncement | null>(null);
  const [universityId, setUniversityId] = useState("");
  const [createForm, setCreateForm] = useState({
    title: "",
    publish_time: new Date().toISOString().slice(0, 10),
    url: "",
    type: "招生公告",
    content: "",
  });

  const fetcher = useCallback(
    (p: { page: number; pageSize: number; q: string }) =>
      fetchAdminAnnouncements({ page: p.page, pageSize: p.pageSize, q: p.q }),
    []
  );

  const { q, setQ, page, setPage, loading, error, items, total, pageSize, search, reload } =
    useAdminList({ fetcher });

  async function handleCreate() {
    if (!universityId || !createForm.title.trim() || !createForm.url.trim()) {
      toast("请填写院校、标题和链接", "error");
      return;
    }
    await createAdminAnnouncement({
      university_id: universityId,
      title: createForm.title,
      publish_time: createForm.publish_time,
      url: createForm.url,
      type: createForm.type || "招生公告",
      content: createForm.content || null,
    });
    toast("公告已创建", "success");
    setCreateOpen(false);
    await reload();
  }

  async function handleDelete(id: string) {
    if (!window.confirm("确定删除该公告？")) return;
    try {
      await deleteAdminAnnouncement(id);
      toast("公告已删除", "success");
      await reload();
    } catch (e) {
      toast(e instanceof Error ? e.message : "删除失败", "error");
    }
  }

  return (
    <AdminModulePage
      title="公告管理"
      subNav={nav.children}
      actions={
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          新建公告
        </Button>
      }
    >
      <FilterBar value={q} onChange={setQ} onSearch={search} placeholder="搜索公告标题" />
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <AdminDataTableShell>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>标题</TableHead>
              <TableHead>类型</TableHead>
              <TableHead>发布日期</TableHead>
              <TableHead>链接</TableHead>
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
              : items.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell className="max-w-sm truncate font-medium">{a.title}</TableCell>
                    <TableCell className="text-muted-foreground">{a.type}</TableCell>
                    <TableCell className="text-muted-foreground">{a.publish_time}</TableCell>
                    <TableCell>
                      <a
                        href={a.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-muted-foreground hover:text-foreground"
                      >
                        打开
                      </a>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setEditing(a);
                          setEditOpen(true);
                        }}
                      >
                        编辑
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive"
                        onClick={() => void handleDelete(a.id)}
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
        title="编辑公告"
        fields={EDIT_FIELDS}
        initial={
          editing
            ? {
                title: editing.title,
                publish_time: editing.publish_time,
                url: editing.url,
                type: editing.type,
                content: "",
              }
            : undefined
        }
        onSubmit={async (values) => {
          if (!editing) return;
          await updateAdminAnnouncement(editing.id, {
            title: values.title,
            publish_time: values.publish_time,
            url: values.url,
            type: values.type || null,
            content: values.content || null,
          });
          toast("公告已更新", "success");
          await reload();
        }}
      />

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>新建公告</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <UniversityPicker value={universityId} onChange={setUniversityId} />
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
