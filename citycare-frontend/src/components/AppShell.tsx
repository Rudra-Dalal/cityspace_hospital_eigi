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
  ShieldCheck,
} from "lucide-react";
import { ROLE_LABEL } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ThemeToggle";
import { InteractiveGradientBackground } from "@/components/InteractiveGradientBackground";

type NavItem = { to: string; label: string; icon: typeof LayoutDashboard };

const NAV: Record<string, NavItem[]> = {
  customer: [
    { to: "/patient/dashboard", label: "My Appointments", icon: LayoutDashboard },
    { to: "/patient/book", label: "Book Consultation", icon: CalendarPlus },
  ],
  doctor: [{ to: "/doctor/dashboard", label: "Clinical Workspace", icon: Stethoscope }],
  hospital_manager: [{ to: "/manager/dashboard", label: "Hospital Operations", icon: Building2 }],
  super_admin: [{ to: "/admin/dashboard", label: "Network Admin", icon: Users }],
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
    <div className="min-h-screen text-foreground flex flex-col selection:bg-primary/25 relative overflow-x-hidden">
      {/* Interactive Ambient Gradient Background */}
      <InteractiveGradientBackground showGrid={true} />

      {/* Top Floating Glass Header */}
      <header className="sticky top-0 z-40 glass-header">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-2.5 sm:px-6 lg:px-8">
          {/* Logo & Brand Identity */}
          <Link
            to={user ? (items[0]?.to ?? "/") : "/"}
            className="flex items-center gap-3 tap-feedback focus-visible:rounded-xl focus-visible:outline-none"
          >
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-primary text-primary-foreground shadow-sm shadow-primary/25 ring-1 ring-black/5 dark:ring-white/10">
              <HeartPulse className="h-5 w-5" />
            </span>
            <div className="flex flex-col">
              <div className="flex items-center gap-1.5">
                <span className="font-display text-base font-bold tracking-tight text-foreground">
                  Medihub
                </span>
                <span className="text-[10px] uppercase font-semibold text-primary/80 bg-primary/10 px-1.5 py-0.2 rounded">
                  CityCare
                </span>
              </div>
              {user ? (
                <span className="text-[11px] font-medium text-muted-foreground capitalize">
                  {ROLE_LABEL[user.role] ?? user.role}
                </span>
              ) : null}
            </div>
          </Link>

          {/* Desktop Navigation Tabs */}
          {items.length > 0 ? (
            <nav className="hidden md:flex items-center gap-1 rounded-2xl bg-secondary/50 p-1 border border-border/40 backdrop-blur-md">
              {items.map((item) => {
                const Icon = item.icon;
                const active = pathname === item.to || pathname.startsWith(`${item.to}/`);
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    className={cn(
                      "flex items-center gap-2 rounded-xl px-4 py-1.5 text-xs font-semibold transition-all tap-feedback",
                      active
                        ? "bg-card text-foreground shadow-subtle border border-border/60"
                        : "text-muted-foreground hover:text-foreground hover:bg-surface/50",
                    )}
                  >
                    <Icon className={cn("h-3.5 w-3.5", active ? "text-primary" : "opacity-70")} />
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          ) : null}

          {/* Right Header Controls (Theme, User, Logout, Mobile Menu) */}
          <div className="flex items-center gap-2.5">
            <ThemeToggle />

            {user ? (
              <div className="hidden sm:flex items-center gap-3 pl-2 border-l border-border/60">
                <div className="flex items-center gap-2">
                  <span className="grid h-8 w-8 place-items-center rounded-xl bg-primary/10 text-xs font-bold text-primary border border-primary/20">
                    {initials}
                  </span>
                  <div className="hidden lg:block text-left">
                    <p className="text-xs font-bold text-foreground leading-tight">
                      {user.first_name} {user.last_name}
                    </p>
                    <p className="text-[10px] text-muted-foreground truncate max-w-[120px]">
                      {user.email}
                    </p>
                  </div>
                </div>

                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleLogout}
                  title="Sign out of Medihub"
                  className="h-8 w-8 rounded-xl text-muted-foreground hover:text-destructive hover:bg-destructive/10 tap-feedback"
                >
                  <LogOut className="h-4 w-4" />
                </Button>
              </div>
            ) : null}

            {/* Mobile Hamburger Toggle */}
            <button
              type="button"
              className="grid h-9 w-9 place-items-center rounded-xl border border-border/80 bg-surface/80 text-foreground md:hidden tap-feedback"
              onClick={() => setOpen((prev) => !prev)}
              aria-label={open ? "Close menu" : "Open menu"}
            >
              {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
            </button>
          </div>
        </div>

        {/* Mobile Navigation Drawer */}
        {open ? (
          <div className="border-t border-border/60 bg-surface/95 backdrop-blur-xl px-4 py-4 md:hidden fade-rise">
            {user ? (
              <div className="mb-3 flex items-center gap-3 border-b border-border/60 pb-3">
                <span className="grid h-9 w-9 place-items-center rounded-xl bg-primary/10 text-xs font-bold text-primary border border-primary/20">
                  {initials}
                </span>
                <div className="min-w-0">
                  <p className="text-xs font-bold text-foreground">
                    {user.first_name} {user.last_name}
                  </p>
                  <p className="text-[11px] text-muted-foreground truncate">{user.email}</p>
                </div>
              </div>
            ) : null}

            <nav className="space-y-1">
              {items.map((item) => {
                const Icon = item.icon;
                const active = pathname === item.to;
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    onClick={() => setOpen(false)}
                    className={cn(
                      "flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-xs font-semibold transition-colors tap-feedback",
                      active
                        ? "bg-primary text-primary-foreground font-bold shadow-soft"
                        : "text-foreground hover:bg-surface",
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    {item.label}
                  </Link>
                );
              })}

              {user ? (
                <button
                  type="button"
                  onClick={() => {
                    setOpen(false);
                    handleLogout();
                  }}
                  className="mt-2 flex w-full items-center gap-2.5 rounded-xl px-3.5 py-2.5 text-left text-xs font-semibold text-destructive transition-colors hover:bg-destructive/10 tap-feedback"
                >
                  <LogOut className="h-4 w-4" />
                  Sign out
                </button>
              ) : null}
            </nav>
          </div>
        ) : null}
      </header>

      {/* Main Workspace Area */}
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-10 relative z-10">
        {children}
      </main>

      {/* Hospital Footer */}
      <footer className="border-t border-border/40 py-6 text-center text-xs text-muted-foreground mt-auto relative z-10">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-primary" />
            <span>© {new Date().getFullYear()} Medihub / CityCare Hospital Network. Verified Clinical Systems.</span>
          </div>
          <div className="flex items-center gap-4 text-[11px]">
            <span>Calm & Secure Healthcare</span>
            <span>•</span>
            <span>24/7 Verified Specialist Network</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
