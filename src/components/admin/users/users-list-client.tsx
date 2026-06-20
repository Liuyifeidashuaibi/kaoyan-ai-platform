"use client";

import { useCallback, useState } from "react";
import Link from "next/link";

import { AdminModulePage } from "@/components/admin/layout/admin-module-page";
import {
  AdminDataTableShell,
  AdminTableFooter,
  formatAdminDate,
} from "@/components/admin/data-table/admin-data-table";
import { FilterBar } from "@/components/admin/shared/filter-bar";
import { Badge } from "@/components/ui/badge";
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
import { fetchAdminUsers, type AdminUser } from "@/lib/admin/api/users";

const nav = adminNavItems.find((item) => item.id === "users")!;

export function UsersListClient() {
  const fetcher = useCallback(
    (p: { page: number; pageSize: number; q: string }) =>
      fetchAdminUsers({ page: p.page, pageSize: p.pageSize, q: p.q }),
    []
  );

  const { q, setQ, page, setPage, loading, error, items, total, pageSize, search } =
    useAdminList<AdminUser>({ fetcher });

  return (
    <AdminModulePage
      title="用户中心"
      description="用户列表、详情与行为统计"
      subNav={nav.children}
      actions={
        <Badge variant="outline" className="font-normal">
          {total} 用户
        </Badge>
      }
    >
      <FilterBar value={q} onChange={setQ} onSearch={search} placeholder="搜索昵称或邮箱" />
      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <AdminDataTableShell>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>用户</TableHead>
              <TableHead>邮箱</TableHead>
              <TableHead>注册时间</TableHead>
              <TableHead className="text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell colSpan={4}>
                      <Skeleton className="h-8 w-full" />
                    </TableCell>
                  </TableRow>
                ))
              : items.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell>
                      <div className="font-medium">{user.nickname || "未命名"}</div>
                      {user.display_id ? (
                        <div className="text-xs text-muted-foreground">ID {user.display_id}</div>
                      ) : null}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{user.email || "—"}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatAdminDate(user.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Link
                        href={`/admin/users/${user.id}`}
                        className="text-sm text-muted-foreground hover:text-foreground"
                      >
                        详情
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
            {!loading && items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="py-12 text-center text-muted-foreground">
                  暂无数据
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
        <AdminTableFooter total={total} page={page} pageSize={pageSize} onPageChange={setPage} />
      </AdminDataTableShell>
    </AdminModulePage>
  );
}
