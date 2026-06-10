"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { SUBJECT_NAME_MAX_LENGTH } from "@/lib/study-timer/constants";

interface SubjectCreateFormProps {
  value: string;
  creating: boolean;
  formError: string | null;
  onChange: (value: string) => void;
  onSubmit: () => void;
}

export function SubjectCreateForm({
  value,
  creating,
  formError,
  onChange,
  onSubmit,
}: SubjectCreateFormProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>新建科目</CardTitle>
        <CardDescription>
          输入科目名称（如：数学、英语、政治），最多 {SUBJECT_NAME_MAX_LENGTH} 字
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="flex flex-col gap-4 sm:flex-row sm:items-end"
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
        >
          <div className="flex-1 space-y-2">
            <Label htmlFor="subject-name">科目名称</Label>
            <Input
              id="subject-name"
              value={value}
              maxLength={SUBJECT_NAME_MAX_LENGTH}
              placeholder="例如：高等数学"
              onChange={(event) => onChange(event.target.value)}
            />
          </div>
          <Button type="submit" disabled={creating || value.trim().length === 0}>
            {creating ? "创建中…" : "创建科目"}
          </Button>
        </form>
        {formError ? (
          <p className="mt-3 text-sm text-destructive">{formError}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}
