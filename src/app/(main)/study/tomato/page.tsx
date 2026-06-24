import dynamic from "next/dynamic";

const TimerPage = dynamic(
  () =>
    import("@/components/timer/timer-page").then((mod) => mod.TimerPage),
  {
    loading: () => (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Loading timer…
      </div>
    ),
  }
);

export default function StudyTomatoPage() {
  return <TimerPage />;
}
