import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string | undefined;
  title: string;
  description?: string | undefined;
  action?: ReactNode;
}) {
  return (
    <header className="mb-8 grid grid-cols-[minmax(0,1fr)_auto] items-end gap-4 sm:flex sm:flex-wrap sm:justify-between">
      <div className="min-w-0">
        {eyebrow ? (
          <p className="mb-1.5 text-xs font-semibold uppercase tracking-[0.16em] text-primary">{eyebrow}</p>
        ) : null}
        <h1 className="font-display text-3xl leading-tight sm:text-4xl">{title}</h1>
        {description ? (
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground sm:text-base">{description}</p>
        ) : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </header>
  );
}

export function Panel({
  title,
  description,
  action,
  className,
  children,
}: {
  title?: string | undefined;
  description?: string | undefined;
  action?: ReactNode;
  className?: string | undefined;
  children: ReactNode;
}) {
  return (
    <section className={cn("surface-panel fade-rise p-5 sm:p-7", className)}>
      {title ? (
        <div className="mb-5 grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 sm:flex sm:flex-wrap sm:justify-between">
          <div className="min-w-0">
            <h2 className="font-display text-xl leading-tight">{title}</h2>
            {description ? <p className="mt-1 text-sm text-muted-foreground">{description}</p> : null}
          </div>
          {action ? <div className="shrink-0">{action}</div> : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export function StatCard({
  label,
  value,
  hint,
  icon,
}: {
  label: string;
  value: ReactNode;
  hint?: string | undefined;
  icon?: ReactNode;
}) {
  return (
    <div className="surface-panel hover-lift fade-rise p-5">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-muted-foreground">{label}</p>
        {icon ? (
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-primary-soft text-accent-foreground">
            {icon}
          </span>
        ) : null}
      </div>
      <p className="mt-3 font-display text-3xl leading-none">{value}</p>
      {hint ? <p className="mt-2 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

export function StatusBadge({ status }: { status?: string | null }) {
  const value = (status ?? "unknown").toString().toLowerCase();
  const tone =
    value.includes("cancel")
      ? "bg-destructive/10 text-destructive"
      : value.includes("complete") || value.includes("done")
        ? "bg-muted text-muted-foreground"
        : value.includes("pending")
          ? "bg-warning/15 text-warning-foreground"
          : value.includes("inactive") || value.includes("suspend")
            ? "bg-muted text-muted-foreground"
            : "bg-success/12 text-success";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold capitalize",
        tone,
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
      {value.replace(/_/g, " ")}
    </span>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string | undefined;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl bg-surface px-6 py-14 text-center">
      <p className="font-display text-lg">{title}</p>
      {description ? (
        <p className="mt-1.5 max-w-sm text-sm text-muted-foreground">{description}</p>
      ) : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export function LoadingRows({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-16 w-full rounded-xl" />
      ))}
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="rounded-xl bg-destructive/10 px-4 py-3 text-sm font-medium text-destructive">
      {message}
    </div>
  );
}
