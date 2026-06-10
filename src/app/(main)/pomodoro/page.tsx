import { PagePlaceholder } from "@/components/layout/page-placeholder";
import { requireAuth } from "@/lib/auth/require-auth";

export default async function PomodoroPage() {
  await requireAuth("/pomodoro");

  return (
    <PagePlaceholder
      title="番茄"
      description="使用番茄钟专注学习，记录时长并同步到学习记录。"
    />
  );
}
