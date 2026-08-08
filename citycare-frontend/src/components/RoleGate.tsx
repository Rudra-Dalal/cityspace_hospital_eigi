import { useEffect, type ReactNode } from "react";
import { useNavigate } from "@tanstack/react-router";
import { ROLE_HOME, type Role } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { AppShell } from "./AppShell";
import { Skeleton } from "@/components/ui/skeleton";

export function RoleGate({ role, children }: { role: Role; children: ReactNode }) {
  const { user, ready, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!ready) return;
    if (!isAuthenticated || !user) {
      navigate({ to: "/", replace: true });
      return;
    }
    if (user.role !== role) {
      navigate({ to: ROLE_HOME[user.role], replace: true });
    }
  }, [ready, isAuthenticated, user, role, navigate]);

  if (!ready || !user || user.role !== role) {
    return (
      <AppShell>
        <div className="space-y-4">
          <Skeleton className="h-10 w-64" />
          <Skeleton className="h-40 w-full rounded-2xl" />
          <Skeleton className="h-40 w-full rounded-2xl" />
        </div>
      </AppShell>
    );
  }

  return <AppShell>{children}</AppShell>;
}
