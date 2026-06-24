export default function SettingsLoading() {
  return (
    <div className="flex flex-col gap-6 p-6 md:p-8">
      <div className="h-8 w-32 animate-pulse rounded-lg bg-muted" />
      <div className="flex flex-col gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-16 animate-pulse rounded-xl bg-muted/70" />
        ))}
      </div>
    </div>
  );
}
