export default function WrongQuestionsLoading() {
  return (
    <div className="flex h-full flex-col gap-4 p-6 md:p-8">
      <div className="h-8 w-40 animate-pulse rounded-lg bg-muted" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-32 animate-pulse rounded-xl bg-muted/70" />
        ))}
      </div>
    </div>
  );
}
