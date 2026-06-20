"use client";

import { useCallback, useState } from "react";

import { AdminRecordDialog } from "@/components/admin/schools/admin-record-dialog";
import { AdminModulePage } from "@/components/admin/layout/admin-module-page";
import {
  AdminDataTableShell,
  AdminTableFooter,
  formatAdminDate,
} from "@/components/admin/data-table/admin-data-table";
import { FilterBar } from "@/components/admin/shared/filter-bar";
import { useAdminToast } from "@/components/admin/shared/admin-toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
  createAdminSchool,
  fetchAdminSchools,
  updateAdminSchool,
  type AdminSchool,
} from "@/lib/admin/api/schools";

const nav = adminNavItems.find((item) => item.id === "schools")!;

const SCHOOL_FIELDS = [
  { key: "name", label: "学校名称", required: true },
  { key: "province", label: "省份" },
  { key: "city", label: "城市" },
  { key: "school_type", label: "类型", placeholder: "综合/理工/师范…" },
  { key: "website", label: "官网" },
  { key: "intro", label: "简介" },
] as const;

export function SchoolsListClient() {
  const { toast } = useAdminToast();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<AdminSchool | null>(null);

  const fetcher = useCallback(
    (p: { page: number; pageSize: number; q: string }) =>
      fetchAdminSchools({ page: p.page, pageSize: p.pageSize, q: p.q }),
    []
  );

  const { q, setQ, page, setPage, loading, error, items, total, pageSize, search, reload } =
    useAdminList({ fetcher });

  async function handleSave(values: Record<string, string>) {
    const body = {
      name: values.name,
      province: values.province || null,
      city: values.city || null,
      school_type: values.school_type || "综合",
      website: values.website || null,
      intro: values.intro || null,
    };
    if (editing) {
      await updateAdminSchool(editing.id, body);
      toast("学校已更新", "success");
    } else {
      await createAdminSchool(body);
      toast("学校已创建", "success");
    }
    await reload();
  }

  return (
    <AdminModulePage
      title="择校中心"
      description="院校数据维护（universities 主表）"
      subNav={nav.children}
      actions={
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="font-normal">
            {total} 学校
          </Badge>
          <Button
            size="sm"
            onClick={() => {
              setEditing(null);
              setDialogOpen(true);
            }}
          >
            新建学校
          </Button>
        </div>
      }
    >
      <FilterBar value={q} onChange={setQ} onSearch={search} placeholder="搜索学校名称" />
      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <AdminDataTableShell>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>学校</TableHead>
              <TableHead>标签</TableHead>
              <TableHead>地区</TableHead>
              <TableHead>类型</TableHead>
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
              : items.map((school) => (
                  <TableRow key={school.id}>
                    <TableCell className="font-medium">{school.name}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {school.level_985 ? (
                          <Badge variant="secondary" className="text-[10px]">
                            985
                          </Badge>
                        ) : null}
                        {school.level_211 ? (
                          <Badge variant="secondary" className="text-[10px]">
                            211
                          </Badge>
                        ) : null}
                        {school.double_first_class ? (
                          <Badge variant="outline" className="text-[10px]">
                            双一流
                          </Badge>
                        ) : null}
                      </div>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {[school.province, school.city].filter(Boolean).join(" · ") || "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {school.school_type || "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatAdminDate(school.updated_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setEditing(school);
                          setDialogOpen(true);
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
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        title={editing ? "编辑学校" : "新建学校"}
        fields={[...SCHOOL_FIELDS]}
        initial={
          editing
            ? {
                name: editing.name,
                province: editing.province ?? "",
                city: editing.city ?? "",
                school_type: editing.school_type ?? "",
                website: editing.website ?? "",
                intro: editing.intro ?? "",
              }
            : undefined
        }
        onSubmit={handleSave}
      />
    </AdminModulePage>
  );
}
