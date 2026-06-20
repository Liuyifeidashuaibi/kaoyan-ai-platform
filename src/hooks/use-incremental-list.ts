"use client";

import { useCallback, useEffect, useState } from "react";

const DEFAULT_PAGE_SIZE = 24;

export function useIncrementalList<T>(items: T[], pageSize = DEFAULT_PAGE_SIZE) {
  const [visibleCount, setVisibleCount] = useState(pageSize);

  useEffect(() => {
    setVisibleCount(pageSize);
  }, [items, pageSize]);

  const visibleItems = items.slice(0, visibleCount);
  const hasMore = visibleCount < items.length;

  const loadMore = useCallback(() => {
    setVisibleCount((count) => Math.min(count + pageSize, items.length));
  }, [items.length, pageSize]);

  return { visibleItems, hasMore, loadMore, total: items.length };
}
