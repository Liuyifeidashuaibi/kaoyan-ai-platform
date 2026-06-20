"use client";

import { useEffect, useState } from "react";

import { Label } from "@/components/ui/label";
import { fetchUniversityOptions, type AdminSchool } from "@/lib/admin/api/schools";

export function UniversityPicker({
  value,
  onChange,
  label = "所属院校",
}: {
  value: string;
  onChange: (id: string) => void;
  label?: string;
}) {
  const [options, setOptions] = useState<AdminSchool[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchUniversityOptions()
      .then(setOptions)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
        disabled={loading}
      >
        <option value="">{loading ? "加载院校…" : "选择院校"}</option>
        {options.map((u) => (
          <option key={u.id} value={u.id}>
            {u.name}
            {u.province ? ` · ${u.province}` : ""}
          </option>
        ))}
      </select>
    </div>
  );
}
