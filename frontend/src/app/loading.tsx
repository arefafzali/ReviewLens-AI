export default function Loading() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl items-center px-4 py-10 sm:px-6">
      <div className="w-full space-y-3 rounded-xl border border-border bg-card p-5 shadow-sm">
        <div className="h-4 w-40 animate-pulse rounded bg-muted" />
        <div className="h-4 w-full animate-pulse rounded bg-muted" />
        <div className="h-4 w-2/3 animate-pulse rounded bg-muted" />
      </div>
    </main>
  );
}
