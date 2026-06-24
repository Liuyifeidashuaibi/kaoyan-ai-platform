export default function TranslatorLoading() {
  return (
    <div className="flex h-full flex-col gap-4 p-6 md:p-8">
      <div className="h-10 w-48 animate-pulse rounded-lg bg-muted" />
      <div className="flex flex-1 gap-4">
        <div className="h-full flex-1 animate-pulse rounded-xl bg-muted/70" />
        <div className="h-full flex-1 animate-pulse rounded-xl bg-muted/70" />
      </div>
    </div>
  );
}
