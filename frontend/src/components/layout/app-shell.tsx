import React from "react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type AppShellProps = {
  title: string;
  subtitle: string;
  children: ReactNode;
  className?: string;
};

export function AppShell({ title, subtitle, children, className }: AppShellProps): ReactNode {
  return (
    <main className={cn("mx-auto flex min-h-screen w-full max-w-5xl flex-col px-4 py-10 sm:px-6", className)}>
      <header className="mb-8 space-y-2">
        <p className="inline-flex rounded-full border border-border bg-card px-3 py-1 text-xs font-medium tracking-wide text-muted-foreground">
          ReviewLens AI
        </p>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
        <p className="max-w-2xl text-sm text-muted-foreground sm:text-base">{subtitle}</p>
      </header>
      {children}
    </main>
  );
}
