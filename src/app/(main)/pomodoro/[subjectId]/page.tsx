import { SubjectTimerPage } from "@/components/study-timer/subject-timer-page";

interface SubjectTimerRouteProps {
  params: Promise<{ subjectId: string }>;
}

export default async function PomodoroSubjectPage({
  params,
}: SubjectTimerRouteProps) {
  const { subjectId } = await params;
  return <SubjectTimerPage subjectId={subjectId} />;
}
