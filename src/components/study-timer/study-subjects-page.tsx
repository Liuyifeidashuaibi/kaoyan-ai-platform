"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { SubjectCreateForm } from "@/components/study-timer/subject-create-form";
import { SubjectListPanel } from "@/components/study-timer/subject-list-panel";
import { useStudySubjects } from "@/hooks/study-timer/use-study-subjects";
import { useStudySync } from "@/hooks/study-timer/use-study-sync";
import { SUBJECT_NAME_DEBOUNCE_MS } from "@/lib/study-timer/constants";

export function StudySubjectsPage() {
  const {
    subjects,
    loading,
    error,
    notice,
    reload,
    createSubject,
  } = useStudySubjects();

  const { syncing, syncMessage } = useStudySync({ onSynced: reload });

  const [draftName, setDraftName] = useState("");
  const [debouncedName, setDebouncedName] = useState("");
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    const timerId = window.setTimeout(() => {
      setDebouncedName(draftName);
    }, SUBJECT_NAME_DEBOUNCE_MS);

    return () => window.clearTimeout(timerId);
  }, [draftName]);

  const canSubmit = useMemo(
    () => debouncedName.trim().length > 0 && !creating,
    [debouncedName, creating]
  );

  const handleCreate = useCallback(async () => {
    if (!canSubmit) {
      return;
    }

    setCreating(true);
    setFormError(null);

    const created = await createSubject({ name: debouncedName.trim() });

    setCreating(false);

    if (created) {
      setDraftName("");
      setDebouncedName("");
      return;
    }

    setFormError("创建失败，请检查科目名称是否重复");
  }, [canSubmit, createSubject, debouncedName]);

  return (
    <div className="flex flex-col gap-6 p-6 md:p-8">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">学习计时</h1>
          <p className="text-muted-foreground">
            创建科目，进入独立计时页开始正向计时或倒计时
          </p>
        </div>
        <a
          href="/pomodoro/stats"
          className="text-sm font-medium text-primary underline-offset-4 hover:underline"
        >
          查看统计看板 →
        </a>
      </div>

      {syncing ? (
        <Alert>
          <AlertDescription>正在同步本地学习数据至云端…</AlertDescription>
        </Alert>
      ) : null}

      {syncMessage ? (
        <Alert>
          <AlertDescription>{syncMessage}</AlertDescription>
        </Alert>
      ) : null}

      {notice ? (
        <Alert>
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      ) : null}

      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <SubjectCreateForm
        value={draftName}
        creating={creating}
        formError={formError}
        onChange={setDraftName}
        onSubmit={() => void handleCreate()}
      />

      <SubjectListPanel subjects={subjects} loading={loading} />
    </div>
  );
}
