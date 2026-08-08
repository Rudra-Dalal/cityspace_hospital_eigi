import { useEffect, useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { HeartPulse, Loader2 } from "lucide-react";
import { ROLE_HOME } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field, fieldErrorClass, fieldInputClass } from "@/components/Field";
import { ErrorNote } from "@/components/ui-kit";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Sign in — CityCare" },
      {
        name: "description",
        content: "Sign in to CityCare to book hospital appointments, view your schedule or manage your hospital.",
      },
      { property: "og:title", content: "Sign in — CityCare" },
      {
        property: "og:description",
        content: "One calm place for patients, doctors and hospitals to manage appointments.",
      },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const { login, user, ready, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (ready && isAuthenticated && user) {
      navigate({ to: ROLE_HOME[user.role], replace: true });
    }
  }, [ready, isAuthenticated, user, navigate]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const next: typeof errors = {};
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) next.email = "Enter a valid email address";
    if (password.length < 6) next.password = "Password must be at least 6 characters";
    setErrors(next);
    setFormError("");
    if (Object.keys(next).length) return;

    setSubmitting(true);
    try {
      const signedIn = await login(email.trim(), password);
      navigate({ to: ROLE_HOME[signedIn.role], replace: true });
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Unable to sign in");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Care that starts with a conversation"
      subtitle="Book with trusted hospitals, keep every visit in one place, and never lose track of a follow-up."
    >
      <form onSubmit={handleSubmit} className="space-y-5" noValidate>
        <div>
          <h2 className="font-display text-2xl leading-tight">Welcome back</h2>
          <p className="mt-1 text-sm text-muted-foreground">Sign in to continue to CityCare.</p>
        </div>

        {formError ? <ErrorNote message={formError} /> : null}

        <Field id="email" label="Email" error={errors.email}>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={cn(fieldInputClass, errors.email && fieldErrorClass)}
          />
        </Field>

        <Field id="password" label="Password" error={errors.password}>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={cn(fieldInputClass, errors.password && fieldErrorClass)}
          />
        </Field>

        <Button type="submit" size="lg" className="w-full rounded-xl" disabled={submitting}>
          {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          Sign in
        </Button>

        <p className="text-center text-sm text-muted-foreground">
          New patient?{" "}
          <Link to="/signup" className="font-semibold text-primary underline-offset-4 hover:underline">
            Create an account
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}

export function AuthLayout({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-surface">
      <div className="mx-auto grid min-h-screen max-w-6xl items-center gap-10 px-4 py-10 sm:px-6 lg:grid-cols-2 lg:gap-16 lg:px-8">
        <div className="fade-rise hidden lg:block">
          <span className="inline-flex items-center gap-2.5 rounded-full bg-card px-4 py-2 shadow-soft">
            <HeartPulse className="h-4 w-4 text-primary" />
            <span className="text-sm font-semibold">CityCare</span>
          </span>
          <h1 className="mt-8 font-display text-5xl leading-[1.05]">{title}</h1>
          <p className="mt-5 max-w-md text-base text-muted-foreground">{subtitle}</p>
          <dl className="mt-10 grid gap-4 sm:grid-cols-2">
            {[
              ["7-day booking window", "Pick a day, see live free slots."],
              ["One record", "Reasons, symptoms and status together."],
              ["Multi-hospital", "Care teams across the whole network."],
              ["Cancel anytime", "Free up your slot in one tap."],
            ].map(([heading, copy]) => (
              <div key={heading} className="surface-panel p-4">
                <dt className="text-sm font-semibold">{heading}</dt>
                <dd className="mt-1 text-xs text-muted-foreground">{copy}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="fade-rise mx-auto w-full max-w-md">
          <div className="mb-6 flex items-center gap-2.5 lg:hidden">
            <span className="grid h-10 w-10 place-items-center rounded-2xl bg-primary text-primary-foreground">
              <HeartPulse className="h-5 w-5" />
            </span>
            <span className="font-display text-xl">CityCare</span>
          </div>
          <div className="surface-panel p-6 sm:p-8">{children}</div>
        </div>
      </div>
    </div>
  );
}
