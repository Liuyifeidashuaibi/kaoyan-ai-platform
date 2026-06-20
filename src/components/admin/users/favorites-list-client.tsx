"use client";

import { useCallback } from "react";
import Link from "next/link";

import { AdminModulePage } from "@/components/admin/layout/admin-module-page";
import {
  AdminDataTableShell,
  AdminTableFooter,
  formatAdminDate,
} from "@/components/admin/data-table/admin-data-table";
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
import { fetchAdminFavorites } from "@/lib/admin/api/users";
import { useAdminList } from "@/hooks/use-admin-list";

const nav = adminNavItems.find((item) => item.id === "users")!;

export function FavoritesListClient() {
  const fetcher = useCallback(
    (p: { page: number; pageSize: number }) =>
      fetchAdminFavorites({ page: p.page, pageSize: p.pageSize }),
    []
  );
  const { page, setPage, loading, error, items, total, pageSize } = useAdminList({
    fetcher: (p) => fetcher(p),
  });

  return (
    <AdminModulePage title="收藏统计" subNav={nav.children}>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <AdminDataTableShell>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>用户</TableHead>
              <TableHead>帖子</TableHead>
              <TableHead>收藏时间</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell colSpan={3}><Skeleton className="h-8 w-full" /></TableCell>
                  </TableRow>
                ))
              : items.map((row, i) => (
                  <TableRow key={`${row.user_id}-${row.post_id}-${i}`}>
                    <TableCell>
                      <Link href={`/admin/users/${row.user_id}`} className="font-mono text-xs hover:underline">
                        {row.user_id.slice(0, 8)}…
                      </Link>
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {row.post_id.slice(0, 8)}…
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatAdminDate(row.created_at)}
                    </TableCell>
                  </TableRow>
                ))}
          </TableBody>
        </Table>
        <AdminTableFooter total={total} page={page} pageSize={pageSize} onPageChange={setPage} />
      </AdminDataTableShell>
    </AdminModulePage>
  );
}
