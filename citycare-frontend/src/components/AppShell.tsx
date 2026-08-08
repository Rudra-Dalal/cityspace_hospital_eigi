import { useState, type ReactNode } from "react";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import {
  CalendarPlus,
  LayoutDashboard,
  LogOut,
  Menu,
  Building2,
  Users,
  Stethoscope,
  HeartPulse,
  X,
} from "lucide-react";
import { ROLE_LABEL } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

type NavItem = { to: string; label: string; icon: typeof LayoutDashboard };

const NAV: Record<string, NavItem[]> = {
  customer: [
    { to: "/patient/dashboard", label: "My appointments", icon: LayoutDashboard },
    { to: "/patient/book", label: "Book appointment", icon: CalendarPlus },
  ],
  doctor: [{ to: "/doctor/dashboard", label: "My schedule", icon: Stethoscope }],
  hospital_manager: [{ to: "/manager/dashboard", label: "Hospital", icon: Building2 }],
  super_admin: [{ to: "/admin/dashboard", label: "Administration", icon: Users }],
};

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const [open, setOpen] = useState(false);

  const items = user ? (NAV[user.role] ?? []) : [];
  const initials = user ? `${user.first_name?.[0] ?? ""}${user.last_name?.[0] ?? ""}`.toUpperCase() : "";

  function handleLogout() {
    logout();
    navigate({ to: "/", replace: true });
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 border-b border-border/70 bg-background/85 backdrop-blur-md">
        <div className="mx-auto grid max-w-7xl grid-cols-[minmax(0,1fr)_auto] items-center gap-4 px-4 py-3 sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-primary text-primary-foreground">
              <HeartPulse className="h-5 w-5" />
            </span>
            <div className="min-w-0">
              <p className="truncate font-display text-lg leading-tight">CityCare</p>
              {user ? (
                <p className="truncate text-xs text-muted-foreground">{ROLE_LABEL[user.role]}</p>
              ) : null}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <nav className="hidden items-center gap-1 md:flex">
              {items.map((item) => {
                const active = pathname === item.to;
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    className={cn(
                      "inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-colors duration-200",
                      active
                        ? "bg-primary-soft text-accent-foreground"
                        : "text-muted-foreground hover:bg-secondary hover:text-foreground",
                    )}
                  >
                    <item.icon className="h-4 w-4" />
                    {item.label}
                  </Link>
                );
              })}
            </nav>

            {user ? (
              <div className="hidden items-center gap-3 md:flex">
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-secondary text-xs font-semibold text-secondary-foreground">
                  {initials}
                </span>
                <Button variant="ghost" size="sm" onClick={handleLogout}>
                  <LogOut className="mr-1.5 h-4 w-4" /> Sign out
                </Button>
              </div>
            ) : null}

            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              aria-label="Toggle menu"
              onClick={() => setOpen((v) => !v)}
            >
              {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </Button>
          </div>
        </div>

        {open ? (
          <div className="border-t border-border/70 bg-background px-4 py-3 md:hidden">
            <nav className="flex flex-col gap-1">
              {items.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  onClick={() => setOpen(false)}
                  className={cn(
                    "inline-flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                    pathname === item.to
                      ? "bg-primary-soft text-accent-foreground"
                      : "text-muted-foreground hover:bg-secondary",
                  )}
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </Link>
              ))}
              <button
                onClick={handleLogout}
                className="mt-1 inline-flex items-center gap-2 rounded-xl px-3 py-2.5 text-left text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary"
              >
                <LogOut className="h-4 w-4" /> Sign out
              </button>
            </nav>
          </div>
        ) : null}
      </header>

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 lg:py-12">{children}</main>
    </div>
  );
}
