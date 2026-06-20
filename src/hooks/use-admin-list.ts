import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/lib/api/client";

export function useAdminList<T>({
  fetcher,
  pageSize = 20,
}: {
  fetcher: (params: { page: number; pageSize: number; q: string }) => Promise<{
    items: T[];
    total: number;
    pageSize: number;
  } | null | undefined>;
  pageSize?: number;
}) {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<T[]>([]);
  const [total, setTotal] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetcher({ page, pageSize, q: query });
      setItems(res?.items ?? []);
      setTotal(res?.total ?? 0);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [fetcher, page, pageSize, query]);

  useEffect(() => {
    void load();
  }, [load]);

  function search() {
    setPage(1);
    setQuery(q);
  }

  return {
    q,
    setQ,
    page,
    setPage,
    loading,
    error,
    items,
    total,
    pageSize,
    search,
    reload: load,
  };
}
