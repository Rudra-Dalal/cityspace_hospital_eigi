import type { ReactNode } from "react";
import {
  AlertCircle,
  ArrowUpRight,
  CheckCircle2,
  Clock,
  HelpCircle,
  RefreshCcw,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

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
    <header className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0 max-w-3xl">
        {eyebrow ? (
          <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-primary">
            <Sparkles className="h-3 w-3" />
            <span>{eyebrow}</span>
          </div>
        ) : null}
        <h1 className="font-display text-3xl font-bold tracking-tight text-foreground sm:text-4xl leading-tight">
          {title}
        </h1>
        {description ? (
          <p className="mt-2 text-sm text-muted-foreground sm:text-base leading-relaxed">
            {description}
          </p>
        ) : null}
      </div>
      {action ? <div className="shrink-0 flex items-center gap-3">{action}</div> : null}
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
    <section
      className={cn("surface-panel fade-rise p-5 sm:p-7 relative overflow-hidden", className)}
    >
      {title ? (
        <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-border/50 pb-4">
          <div className="min-w-0">
            <h2 className="font-display text-lg font-bold tracking-tight text-foreground sm:text-xl">
              {title}
            </h2>
            {description ? (
              <p className="mt-1 text-xs text-muted-foreground sm:text-sm">{description}</p>
            ) : null}
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
    <div className="surface-panel hover-lift fade-rise p-5 flex flex-col justify-between">
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {label}
        </p>
        {icon ? (
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary shadow-subtle">
            {icon}
          </span>
        ) : null}
      </div>
      <div className="mt-4">
        <p className="font-display text-3xl font-bold tracking-tight text-foreground">{value}</p>
        {hint ? <p className="mt-1.5 text-xs text-muted-foreground font-medium">{hint}</p> : null}
      </div>
    </div>
  );
}

export function StatusBadge({ status }: { status?: string | null }) {
  const value = (status ?? "unknown").toString().toLowerCase();

  let tone = "bg-muted text-muted-foreground border-border/50";
  let dotColor = "bg-muted-foreground";

  if (
    value.includes("cancel") ||
    value.includes("reject") ||
    value.includes("inactive") ||
    value.includes("suspend")
  ) {
    tone = "bg-destructive/10 text-destructive border-destructive/20";
    dotColor = "bg-destructive";
  } else if (value.includes("complete") || value.includes("done")) {
    tone = "bg-secondary text-secondary-foreground border-border";
    dotColor = "bg-muted-foreground";
  } else if (value.includes("pending") || value.includes("wait") || value.includes("scheduled")) {
    tone = "bg-warning/15 text-warning-foreground border-warning/30";
    dotColor = "bg-warning";
  } else if (
    value.includes("active") ||
    value.includes("booked") ||
    value.includes("confirm") ||
    value.includes("accepted")
  ) {
    tone = "bg-success/15 text-success border-success/30";
    dotColor = "bg-success";
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize border shadow-subtle tracking-wide",
        tone,
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full shrink-0", dotColor)} />
      {value.replace(/_/g, " ")}
    </span>
  );
}

export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string;
  description?: string | undefined;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border/80 bg-surface/60 px-6 py-12 text-center fade-rise">
      <div className="grid h-12 w-12 place-items-center rounded-2xl bg-secondary/80 text-muted-foreground shadow-subtle mb-3">
        {icon || <HelpCircle className="h-6 w-6 opacity-60" />}
      </div>
      <p className="font-display text-base font-semibold text-foreground">{title}</p>
      {description ? (
        <p className="mt-1.5 max-w-sm text-xs sm:text-sm text-muted-foreground leading-relaxed">
          {description}
        </p>
      ) : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export function LoadingRows({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3.5">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex items-center justify-between gap-4 rounded-2xl border border-border/60 bg-card p-4 shadow-subtle"
        >
          <div className="flex items-center gap-3 w-full">
            <Skeleton className="h-10 w-10 rounded-xl shrink-0" />
            <div className="space-y-2 w-full max-w-md">
              <Skeleton className="h-4 w-3/4 rounded-md" />
              <Skeleton className="h-3 w-1/2 rounded-md" />
            </div>
          </div>
          <Skeleton className="h-8 w-20 rounded-xl shrink-0 hidden sm:block" />
        </div>
      ))}
    </div>
  );
}

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-destructive/30 bg-destructive/10 p-4 text-sm font-medium text-destructive fade-rise">
      <div className="flex items-center gap-2.5 min-w-0">
        <AlertCircle className="h-5 w-5 shrink-0" />
        <span className="truncate">{message}</span>
      </div>
      {onRetry ? (
        <Button
          size="sm"
          variant="outline"
          onClick={onRetry}
          className="rounded-xl border-destructive/30 text-destructive hover:bg-destructive/15 tap-feedback"
        >
          <RefreshCcw className="mr-1.5 h-3.5 w-3.5" />
          Retry
        </Button>
      ) : null}
    </div>
  );
}
