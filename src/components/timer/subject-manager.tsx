"use client";

import { useState } from "react";
import { ChevronDown, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { TimerSubject } from "./types";
import { cn } from "@/lib/utils";

interface SubjectManagerProps {
  subjects: TimerSubject[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onAdd: (name: string) => Promise<string | null>;
  disabled?: boolean;
  saving?: boolean;
}

export function SubjectManager({
  subjects,
  selectedId,
  onSelect,
  onAdd,
  disabled,
  saving,
}: SubjectManagerProps) {
  const [name, setName] = useState("");

  async function handleAdd() {
    const trimmed = name.trim();
    if (!trimmed) return;

    const id = await onAdd(trimmed);
    if (id) {
      onSelect(id);
      setName("");
    }
  }

  return (
    <section className="rounded-3xl bg-white p-5 shadow-[0_4px_24px_rgba(0,0,0,0.06)] ring-1 ring-black/[0.03] sm:p-6">
      <label
        htmlFor="timer-subject-select"
        className="text-sm font-medium text-neutral-500"
      >
        Subject
      </label>

      <div className="relative mt-3">
        <select
          id="timer-subject-select"
          value={selectedId ?? ""}
          disabled={disabled || subjects.length === 0}
          onChange={(e) => onSelect(e.target.value)}
          className={cn(
            "h-10 w-full appearance-none rounded-2xl border border-neutral-200 bg-neutral-50/80 px-4 pr-10 text-sm font-medium text-neutral-900",
            "focus:outline-none focus:ring-2 focus:ring-neutral-200",
            (disabled || subjects.length === 0) && "opacity-50"
          )}
        >
          {subjects.length === 0 ? (
            <option value="">No subjects yet</option>
          ) : (
            subjects.map((subject) => (
              <option key={subject.id} value={subject.id}>
                {subject.name}
              </option>
            ))
          )}
        </select>
        <ChevronDown className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-neutral-400" />
      </div>

      <div className="mt-4 flex flex-col gap-2 sm:flex-row">
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Enter Subject"
          disabled={disabled || saving}
          maxLength={20}
          className="h-10 rounded-2xl border-neutral-200 bg-neutral-50/80 sm:flex-1"
          onKeyDown={(e) => {
            if (e.key === "Enter") void handleAdd();
          }}
        />
        <Button
          type="button"
          onClick={() => void handleAdd()}
          disabled={disabled || saving || !name.trim()}
          className="h-10 shrink-0 rounded-2xl px-5"
        >
          <Plus className="mr-1 size-4" />
          Add
        </Button>
      </div>
    </section>
  );
}
