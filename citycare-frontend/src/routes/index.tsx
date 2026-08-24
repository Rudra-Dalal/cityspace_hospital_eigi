import { useEffect, useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import {
  HeartPulse,
  Loader2,
  Calendar,
  ShieldCheck,
  Stethoscope,
  Clock,
  CheckCircle2,
} from "lucide-react";
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
      { title: "Sign in — CityCare Hospital Network" },
      {
        name: "description",
        content:
          "Sign in to CityCare to book hospital appointments, view your schedule or manage your hospital.",
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
      setFormError(
        error instanceof Error
          ? error.message
          : "Unable to sign in. Please verify your credentials.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Calm, connected healthcare at your fingertips."
      subtitle="Discover top hospital branches, schedule verified specialist consultations, and access electronic prescriptions in one serene portal."
    >
      <form onSubmit={handleSubmit} className="space-y-5" noValidate>
        <div>
          <h2 className="font-display text-2xl font-bold tracking-tight text-foreground">
            Welcome back
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Sign in with your email to access your CityCare account.
          </p>
        </div>

        {formError ? <ErrorNote message={formError} /> : null}

        <Field id="email" label="Email Address" error={errors.email}>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={cn(fieldInputClass, errors.email && fieldErrorClass, "rounded-xl h-11")}
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
            className={cn(fieldInputClass, errors.password && fieldErrorClass, "rounded-xl h-11")}
          />
        </Field>

        <Button
          type="submit"
          size="lg"
          className="w-full rounded-xl font-semibold shadow-soft tap-feedback h-11"
          disabled={submitting}
        >
          {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          Sign In to CityCare
        </Button>

        <div className="pt-2 text-center">
          <p className="text-sm text-muted-foreground">
            Don't have an account?{" "}
            <Link
              to="/signup"
              className="font-semibold text-primary underline-offset-4 hover:underline transition-colors tap-feedback"
            >
              Create Patient Account
            </Link>
          </p>
        </div>
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
    <div className="min-h-screen bg-surface flex items-center justify-center p-4 sm:p-6 lg:p-12 relative overflow-hidden">
      {/* Subtle Background Glow Elements */}
      <div className="absolute top-[-10%] left-[-5%] h-[450px] w-[450px] rounded-full bg-primary/8 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-5%] h-[450px] w-[450px] rounded-full bg-success/8 blur-[120px] pointer-events-none" />

      <div className="mx-auto grid w-full max-w-6xl items-center gap-10 lg:grid-cols-2 lg:gap-16">
        {/* Left Visual Column */}
        <div className="fade-rise hidden lg:flex flex-col justify-between space-y-10">
          <div>
            <span className="inline-flex items-center gap-2 rounded-full border border-border/80 bg-card px-4 py-1.5 shadow-subtle">
              <HeartPulse className="h-4 w-4 text-primary" />
              <span className="text-xs font-semibold uppercase tracking-wider text-foreground">
                CityCare Network
              </span>
            </span>
            <h1 className="mt-8 font-display text-4xl font-bold tracking-tight text-foreground xl:text-5xl leading-[1.12]">
              {title}
            </h1>
            <p className="mt-4 max-w-lg text-base text-muted-foreground leading-relaxed">
              {subtitle}
            </p>
          </div>

          <div className="grid gap-3.5 sm:grid-cols-2">
            {[
              {
                icon: <Calendar className="h-4 w-4 text-primary" />,
                title: "Live Doctor Slots",
                desc: "Real-time 7-day appointment matrix with zero double-booking.",
              },
              {
                icon: <Stethoscope className="h-4 w-4 text-primary" />,
                title: "Multi-Hospital Network",
                desc: "Explore verified branches and specialist physicians.",
              },
              {
                icon: <ShieldCheck className="h-4 w-4 text-primary" />,
                title: "Digital Prescriptions",
                desc: "Official clinician diagnoses and downloadable PDF records.",
              },
              {
                icon: <Clock className="h-4 w-4 text-primary" />,
                title: "Immediate AI Assistant",
                desc: "Triage health queries and clarify prescriptions 24/7.",
              },
            ].map((feat) => (
              <div
                key={feat.title}
                className="surface-panel p-4 hover-lift flex flex-col justify-between"
              >
                <div className="flex items-center gap-2.5">
                  <span className="grid h-7 w-7 place-items-center rounded-lg bg-primary/10">
                    {feat.icon}
                  </span>
                  <p className="text-xs font-bold text-foreground">{feat.title}</p>
                </div>
                <p className="mt-2 text-[11px] text-muted-foreground leading-normal">{feat.desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Right Form Card */}
        <div className="fade-rise mx-auto w-full max-w-md">
          <div className="mb-6 flex items-center gap-3 lg:hidden">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary text-primary-foreground shadow-sm shadow-primary/20">
              <HeartPulse className="h-5 w-5" />
            </span>
            <span className="font-display text-2xl font-bold tracking-tight">CityCare</span>
          </div>
          <div className="surface-panel p-6 sm:p-9 shadow-soft border border-border/80 bg-card">
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
