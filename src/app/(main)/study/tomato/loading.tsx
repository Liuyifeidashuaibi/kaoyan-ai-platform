export default function TimerLoading() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="h-48 w-48 animate-pulse rounded-full bg-muted" />
        <div className="h-8 w-32 animate-pulse rounded-lg bg-muted/70" />
      </div>
    </div>
  );
}
