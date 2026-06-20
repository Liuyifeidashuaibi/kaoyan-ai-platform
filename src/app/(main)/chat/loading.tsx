export default function ChatLoading() {
  return (
    <div className="flex h-full min-h-[50vh] flex-col">
      <div className="flex flex-1 flex-col gap-4 p-4">
        <div className="ml-auto h-16 w-2/3 max-w-md animate-pulse rounded-2xl bg-muted" />
        <div className="h-24 w-4/5 max-w-lg animate-pulse rounded-2xl bg-muted/70" />
      </div>
      <div className="border-t border-border p-4">
        <div className="h-12 w-full animate-pulse rounded-xl bg-muted" />
      </div>
    </div>
  );
}
