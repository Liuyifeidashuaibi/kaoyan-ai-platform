"use client";

import { useEffect, useState } from "react";
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

type Field = {
  key: string;
  label: string;
  placeholder?: string;
  required?: boolean;
};

export function AdminRecordDialog({
  open,
  onOpenChange,
  title,
  fields,
  initial,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  fields: Field[];
  initial?: Record<string, string>;
  onSubmit: (values: Record<string, string>) => Promise<void>;
}) {
  const { toast } = useAdminToast();
  const [values, setValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    const next: Record<string, string> = {};
    for (const field of fields) {
      next[field.key] = initial?.[field.key] ?? "";
    }
    setValues(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reset when dialog opens
  }, [open, initial]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    for (const field of fields) {
      if (field.required && !values[field.key]?.trim()) {
        toast(`请填写${field.label}`, "error");
        return;
      }
    }
    setLoading(true);
    try {
      await onSubmit(values);
      onOpenChange(false);
    } catch (err) {
      toast(err instanceof Error ? err.message : "保存失败", "error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={(e) => void handleSubmit(e)}>
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            {fields.map((field) => (
              <div key={field.key} className="grid gap-2">
                <Label htmlFor={field.key}>{field.label}</Label>
                <Input
                  id={field.key}
                  value={values[field.key] ?? ""}
                  placeholder={field.placeholder}
                  onChange={(e) =>
                    setValues((prev) => ({ ...prev, [field.key]: e.target.value }))
                  }
                />
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              取消
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? "保存中…" : "保存"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
