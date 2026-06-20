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
  createAdminCollege,
  fetchAdminColleges,
  updateAdminCollege,
  type AdminCollege,
} from "@/lib/admin/api/schools";

const nav = adminNavItems.find((item) => item.id === "schools")!;

const EDIT_FIELDS = [
  { key: "name", label: "学院名称", required: true },
  { key: "official_site", label: "官网" },
];

export function CollegesListClient() {
  const { toast } = useAdminToast();
  const [editOpen, setEditOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<AdminCollege | null>(null);
  const [universityId, setUniversityId] = useState("");
  const [createName, setCreateName] = useState("");
  const [createSite, setCreateSite] = useState("");

  const fetcher = useCallback(
    (p: { page: number; pageSize: number; q: string }) =>
      fetchAdminColleges({ page: p.page, pageSize: p.pageSize, q: p.q }),
    []
  );

  const { q, setQ, page, setPage, loading, error, items, total, pageSize, search, reload } =
    useAdminList({ fetcher });

  async function handleCreate() {
    if (!universityId || !createName.trim()) {
      toast("请选择院校并填写学院名称", "error");
      return;
    }
    await createAdminCollege({
      university_id: universityId,
      name: createName,
      official_site: createSite || null,
    });
    toast("学院已创建", "success");
    setCreateOpen(false);
    await reload();
  }

  return (
    <AdminModulePage
      title="学院管理"
      description="学院目录维护"
      subNav={nav.children}
      actions={
        <Button
          size="sm"
          onClick={() => {
            setUniversityId("");
            setCreateName("");
            setCreateSite("");
            setCreateOpen(true);
          }}
        >
          新建学院
        </Button>
      }
    >
      <FilterBar value={q} onChange={setQ} onSearch={search} placeholder="搜索学院名称" />
      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <AdminDataTableShell>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>学院</TableHead>
              <TableHead>官网</TableHead>
              <TableHead>院校 ID</TableHead>
              <TableHead>更新时间</TableHead>
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
              : items.map((college) => (
                  <TableRow key={college.id}>
                    <TableCell className="font-medium">{college.name}</TableCell>
                    <TableCell className="max-w-xs truncate text-muted-foreground">
                      {college.official_site ? (
                        <a
                          href={college.official_site}
                          target="_blank"
                          rel="noreferrer"
                          className="hover:underline"
                        >
                          {college.official_site}
                        </a>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {college.university_id.slice(0, 8)}…
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatAdminDate(college.updated_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setEditing(college);
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
        title="编辑学院"
        fields={EDIT_FIELDS}
        initial={
          editing
            ? { name: editing.name, official_site: editing.official_site ?? "" }
            : undefined
        }
        onSubmit={async (values) => {
          if (!editing) return;
          await updateAdminCollege(editing.id, {
            name: values.name,
            official_site: values.official_site || null,
          });
          toast("学院已更新", "success");
          await reload();
        }}
      />

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>新建学院</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <UniversityPicker value={universityId} onChange={setUniversityId} />
            <div className="grid gap-2">
              <Label>学院名称</Label>
              <Input value={createName} onChange={(e) => setCreateName(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>官网</Label>
              <Input value={createSite} onChange={(e) => setCreateSite(e.target.value)} />
            </div>
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
