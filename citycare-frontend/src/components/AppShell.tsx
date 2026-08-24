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
  User,
} from "lucide-react";
import { ROLE_LABEL } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

type NavItem = { to: string; label: string; icon: typeof LayoutDashboard };

const NAV: Record<string, NavItem[]> = {
  customer: [
    { to: "/patient/dashboard", label: "My Appointments", icon: LayoutDashboard },
    { to: "/patient/book", label: "Book Consultation", icon: CalendarPlus },
  ],
  doctor: [{ to: "/doctor/dashboard", label: "Clinical Schedule", icon: Stethoscope }],
  hospital_manager: [{ to: "/manager/dashboard", label: "Hospital Management", icon: Building2 }],
  super_admin: [{ to: "/admin/dashboard", label: "Administration", icon: Users }],
};

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const [open, setOpen] = useState(false);

  const items = user ? (NAV[user.role] ?? []) : [];
  const initials = user
    ? `${user.first_name?.[0] ?? ""}${user.last_name?.[0] ?? ""}`.toUpperCase() || "U"
    : "";

  function handleLogout() {
    logout();
    navigate({ to: "/", replace: true });
  }

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col selection:bg-primary/20 selection:text-primary">
      {/* Top Glass Header */}
      <header className="sticky top-0 z-40 glass-header">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-2.5 sm:px-6 lg:px-8">
          {/* Logo & Brand */}
          <Link
            to={user ? (items[0]?.to ?? "/") : "/"}
            className="flex items-center gap-3 tap-feedback focus-visible:rounded-xl focus-visible:outline-none"
          >
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-primary text-primary-foreground shadow-sm shadow-primary/20 ring-1 ring-black/5 dark:ring-white/10">
              <HeartPulse className="h-5 w-5" />
            </span>
            <div className="min-w-0">
              <span className="font-display text-lg font-bold tracking-tight text-foreground block leading-none">
                CityCare
              </span>
              {user ? (
                <span className="mt-0.5 inline-block text-[11px] font-medium text-muted-foreground leading-tight">
                  {ROLE_LABEL[user.role]}
                </span>
              ) : (
                <span className="mt-0.5 inline-block text-[11px] font-medium text-muted-foreground leading-tight">
                  Hospital Network
                </span>
              )}
            </div>
          </Link>

          {/* Desktop Navigation */}
          <div className="flex items-center gap-3">
            {items.length > 0 ? (
              <nav className="hidden items-center gap-1 rounded-full border border-border/60 bg-secondary/50 p-1 backdrop-blur-md md:flex">
                {items.map((item) => {
                  const active = pathname === item.to;
                  return (
                    <Link
                      key={item.to}
                      to={item.to}
                      className={cn(
                        "inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-xs font-semibold tracking-wide transition-all duration-200",
                        active
                          ? "bg-card text-foreground shadow-subtle ring-1 ring-border/50"
                          : "text-muted-foreground hover:text-foreground hover:bg-card/40",
                      )}
                    >
                      <item.icon
                        className={cn(
                          "h-3.5 w-3.5",
                          active ? "text-primary" : "text-muted-foreground",
                        )}
                      />
                      {item.label}
                    </Link>
                  );
                })}
              </nav>
            ) : null}

            {/* User Profile & Actions */}
            {user ? (
              <div className="hidden items-center gap-2 md:flex pl-2 border-l border-border/60">
                <div className="flex items-center gap-2 rounded-full bg-secondary/40 px-2.5 py-1 text-xs font-medium text-foreground">
                  <span className="grid h-6 w-6 place-items-center rounded-full bg-primary/10 text-[10px] font-bold text-primary">
                    {initials}
                  </span>
                  <span className="max-w-[120px] truncate">
                    {user.first_name} {user.last_name}
                  </span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleLogout}
                  className="rounded-full text-xs font-medium text-muted-foreground hover:text-destructive hover:bg-destructive/10 tap-feedback"
                >
                  <LogOut className="mr-1.5 h-3.5 w-3.5" />
                  Sign out
                </Button>
              </div>
            ) : null}

            {/* Mobile Menu Toggle Button */}
            {items.length > 0 || user ? (
              <Button
                variant="ghost"
                size="icon"
                className="rounded-xl md:hidden tap-feedback"
                aria-label="Toggle menu"
                onClick={() => setOpen((v) => !v)}
              >
                {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
              </Button>
            ) : null}
          </div>
        </div>

        {/* Mobile Dropdown Sheet */}
        {open ? (
          <div className="border-t border-border/60 bg-background/95 backdrop-blur-xl px-4 py-3 md:hidden fade-rise">
            {user ? (
              <div className="mb-3 flex items-center gap-3 border-b border-border/50 pb-3 px-2">
                <span className="grid h-8 w-8 place-items-center rounded-full bg-primary/15 text-xs font-bold text-primary">
                  {initials}
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold truncate leading-tight">
                    {user.first_name} {user.last_name}
                  </p>
                  <p className="text-xs text-muted-foreground truncate">{user.email}</p>
                </div>
              </div>
            ) : null}

            <nav className="flex flex-col gap-1">
              {items.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  onClick={() => setOpen(false)}
                  className={cn(
                    "flex items-center gap-2.5 rounded-xl px-3.5 py-2.5 text-sm font-medium transition-colors tap-feedback",
                    pathname === item.to
                      ? "bg-primary/10 text-primary font-semibold"
                      : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
                  )}
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </Link>
              ))}

              {user ? (
                <button
                  type="button"
                  onClick={() => {
                    setOpen(false);
                    handleLogout();
                  }}
                  className="mt-2 flex w-full items-center gap-2.5 rounded-xl px-3.5 py-2.5 text-left text-sm font-medium text-destructive transition-colors hover:bg-destructive/10 tap-feedback"
                >
                  <LogOut className="h-4 w-4" />
                  Sign out
                </button>
              ) : null}
            </nav>
          </div>
        ) : null}
      </header>

      {/* Main Content Area */}
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-10">
        {children}
      </main>

      {/* Subtle Footer */}
      <footer className="border-t border-border/40 py-6 text-center text-xs text-muted-foreground">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p>© {new Date().getFullYear()} CityCare Hospital Network. All rights reserved.</p>
          <div className="flex items-center gap-4 text-[11px]">
            <span>Calm & Secure Healthcare</span>
            <span>•</span>
            <span>24/7 Verified Physicians</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
