"use client";

import { useCallback } from "react";
import Link from "next/link";

import { AdminModulePage } from "@/components/admin/layout/admin-module-page";
import {
  AdminDataTableShell,
  AdminTableFooter,
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
import { fetchAdminPostStats } from "@/lib/admin/api/users";
import { useAdminList } from "@/hooks/use-admin-list";

const nav = adminNavItems.find((item) => item.id === "users")!;

export function PostStatsListClient() {
  const fetcher = useCallback(
    (p: { page: number; pageSize: number }) =>
      fetchAdminPostStats({ page: p.page, pageSize: p.pageSize }),
    []
  );
  const { page, setPage, loading, error, items, total, pageSize } = useAdminList({
    fetcher: (p) => fetcher(p),
  });

  return (
    <AdminModulePage title="发帖统计" description="按作者聚合发帖量" subNav={nav.children}>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <AdminDataTableShell>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>作者</TableHead>
              <TableHead className="text-right">发帖数</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell colSpan={2}><Skeleton className="h-8 w-full" /></TableCell>
                  </TableRow>
                ))
              : items.map((row) => (
                  <TableRow key={row.author_id}>
                    <TableCell>
                      <Link
                        href={`/admin/users/${row.author_id}`}
                        className="font-mono text-xs hover:underline"
                      >
                        {row.author_id.slice(0, 8)}…
                      </Link>
                    </TableCell>
                    <TableCell className="text-right tabular-nums font-medium">
                      {row.post_count}
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
