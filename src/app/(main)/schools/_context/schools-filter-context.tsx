"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

const STORAGE_KEY = "schools_global_filter";

export interface SchoolsGlobalFilter {
  level985: boolean;
  level211: boolean;
  doubleFirstClass: boolean;
}

interface SchoolsFilterContextValue {
  filter: SchoolsGlobalFilter;
  setFilter: (f: SchoolsGlobalFilter) => void;
  /** 当前没有任何层次被勾选（防呆：不允许全不选） */
  hasAnyLevel: boolean;
}

const defaultFilter: SchoolsGlobalFilter = {
  level985: true,
  level211: true,
  doubleFirstClass: true,
};

const SchoolsFilterContext = createContext<SchoolsFilterContextValue>({
  filter: defaultFilter,
  setFilter: () => {},
  hasAnyLevel: true,
});

export function SchoolsFilterProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [filter, setFilterState] = useState<SchoolsGlobalFilter>(defaultFilter);

  // 从 localStorage 恢复
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved) as Partial<SchoolsGlobalFilter>;
        const restored: SchoolsGlobalFilter = {
          level985: parsed.level985 ?? true,
          level211: parsed.level211 ?? true,
          doubleFirstClass: parsed.doubleFirstClass ?? true,
        };
        // 防呆：如果全部为 false，重置为全选
        if (!restored.level985 && !restored.level211 && !restored.doubleFirstClass) {
          setFilterState(defaultFilter);
        } else {
          setFilterState(restored);
        }
      }
    } catch {
      // localStorage 不可用时使用默认值
    }
  }, []);

  const setFilter = useCallback((f: SchoolsGlobalFilter) => {
    // 防呆：不允许全部取消
    if (!f.level985 && !f.level211 && !f.doubleFirstClass) return;
    setFilterState(f);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(f));
    } catch {
      // ignore
    }
  }, []);

  const hasAnyLevel =
    filter.level985 || filter.level211 || filter.doubleFirstClass;

  return (
    <SchoolsFilterContext.Provider value={{ filter, setFilter, hasAnyLevel }}>
      {children}
    </SchoolsFilterContext.Provider>
  );
}

export function useSchoolsFilter() {
  return useContext(SchoolsFilterContext);
}
