import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  HeadContent,
  Scripts,
} from "@tanstack/react-router";
import { useEffect, type ReactNode } from "react";

import appCss from "../styles.css?url";
import { reportLovableError } from "../lib/lovable-error-reporting";
import { AuthProvider } from "../lib/auth";
import { ThemeProvider } from "../lib/theme";
import { Toaster } from "@/components/ui/sonner";
import { HeartPulse, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center fade-rise">
        <span className="grid h-16 w-16 place-items-center rounded-2xl bg-primary/10 text-primary mx-auto mb-4 shadow-subtle">
          <HeartPulse className="h-8 w-8" />
        </span>
        <h1 className="font-display text-6xl font-bold tracking-tight text-foreground">404</h1>
        <h2 className="mt-3 font-display text-xl font-semibold text-foreground">Page not found</h2>
        <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
          The healthcare resource or screen you requested doesn't exist or has been relocated.
        </p>
        <div className="mt-6">
          <Button asChild className="rounded-xl font-semibold tap-feedback shadow-soft">
            <Link to="/">Return to Dashboard</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}

function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  console.error(error);
  const router = useRouter();
  useEffect(() => {
    reportLovableError(error, { boundary: "tanstack_root_error_component" });
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center fade-rise surface-panel p-8">
        <h1 className="font-display text-xl font-bold tracking-tight text-foreground">
          System Recovery Notice
        </h1>
        <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
          We encountered an unexpected issue while rendering this view. Your session and records remain safe.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Button
            onClick={() => {
              router.invalidate();
              reset();
            }}
            className="rounded-xl font-semibold tap-feedback shadow-soft"
          >
            <RefreshCw className="mr-2 h-4 w-4" /> Try again
          </Button>
          <Button asChild variant="outline" className="rounded-xl font-semibold tap-feedback">
            <Link to="/">Go Home</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "Medihub / CityCare — Hospital Network & Consultation Platform" },
      {
        name: "description",
        content:
          "Medihub connects patients, specialist physicians, and hospital networks in one calm, clinical workspace.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
    links: [
      { rel: "stylesheet", href: appCss },
      { rel: "icon", href: "/favicon.ico", type: "image/x-icon" },
    ],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootShell({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <HeadContent />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <Outlet />
          <Toaster position="top-right" richColors />
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
