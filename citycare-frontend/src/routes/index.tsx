import { useEffect, useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import {
  HeartPulse,
  Loader2,
  Calendar,
  ShieldCheck,
  Stethoscope,
  Clock,
  Sparkles,
} from "lucide-react";
import { ROLE_HOME } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field, fieldErrorClass, fieldInputClass } from "@/components/Field";
import { ErrorNote } from "@/components/ui-kit";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "@/components/ThemeToggle";
import { InteractiveGradientBackground } from "@/components/InteractiveGradientBackground";

export const Route = createFileRoute("/")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Sign in — Medihub / CityCare Hospital Platform" },
      {
        name: "description",
        content:
          "Sign in to Medihub to schedule specialist hospital appointments, access medical prescriptions, or manage clinic schedules.",
      },
      { property: "og:title", content: "Sign in — Medihub" },
      {
        property: "og:description",
        content: "Calm, verified healthcare platform connecting patients, specialist physicians, and hospital networks.",
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
      title="Calm, verified healthcare for every patient & physician."
      subtitle="Discover accredited hospital facilities, book specialist consultations in real time, and access authenticated electronic medical prescriptions."
    >
      <form onSubmit={handleSubmit} className="space-y-5" noValidate>
        <div>
          <h2 className="font-display text-2xl font-bold tracking-tight text-foreground">
            Sign In to Medihub
          </h2>
          <p className="mt-1 text-xs sm:text-sm text-muted-foreground">
            Enter your clinical credentials or patient account email to proceed.
          </p>
        </div>

        {formError ? <ErrorNote message={formError} /> : null}

        <Field id="email" label="Email Address" error={errors.email}>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            placeholder="admin@citycare.clinic"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={cn(fieldInputClass, errors.email && fieldErrorClass, "rounded-xl h-11 text-sm")}
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
            className={cn(fieldInputClass, errors.password && fieldErrorClass, "rounded-xl h-11 text-sm")}
          />
        </Field>

        <Button
          type="submit"
          size="lg"
          className="w-full rounded-xl font-bold shadow-soft tap-feedback h-11"
          disabled={submitting}
        >
          {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          Access Clinical Workspace
        </Button>

        <div className="pt-2 text-center border-t border-border/50">
          <p className="text-xs sm:text-sm text-muted-foreground">
            New to the hospital network?{" "}
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
    <div className="min-h-screen flex flex-col justify-between p-4 sm:p-6 lg:p-12 relative overflow-hidden">
      {/* Interactive Ambient Gradient Background */}
      <InteractiveGradientBackground showGrid={true} />

      {/* Top Floating Brand Header */}
      <div className="mx-auto w-full max-w-6xl flex items-center justify-between pb-6 relative z-10">
        <div className="flex items-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-primary text-primary-foreground shadow-sm shadow-primary/25">
            <HeartPulse className="h-5 w-5" />
          </span>
          <span className="font-display text-lg font-bold tracking-tight text-foreground">
            Medihub
          </span>
          <span className="text-[10px] uppercase font-semibold text-primary/80 bg-primary/10 px-1.5 py-0.5 rounded-md">
            CityCare
          </span>
        </div>
        <ThemeToggle />
      </div>

      {/* Main Content Grid */}
      <div className="mx-auto grid w-full max-w-6xl items-center gap-10 lg:grid-cols-2 lg:gap-16 my-auto relative z-10">
        {/* Left Visual Column */}
        <div className="fade-rise hidden lg:flex flex-col justify-between space-y-8">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-border/80 bg-card/80 backdrop-blur-md px-4 py-1.5 shadow-subtle">
              <Sparkles className="h-3.5 w-3.5 text-primary" />
              <span className="text-[11px] font-semibold uppercase tracking-wider text-foreground">
                Verified Hospital Network
              </span>
            </div>
            <h1 className="mt-6 font-display text-4xl font-bold tracking-tight text-foreground xl:text-5xl leading-[1.12]">
              {title}
            </h1>
            <p className="mt-4 max-w-lg text-sm sm:text-base text-muted-foreground leading-relaxed">
              {subtitle}
            </p>
          </div>

          <div className="grid gap-3.5 sm:grid-cols-2">
            {[
              {
                icon: <Calendar className="h-4 w-4 text-primary" />,
                title: "Live Doctor Scheduling",
                desc: "Real-time 7-day appointment matrix with verified slot availability.",
              },
              {
                icon: <Stethoscope className="h-4 w-4 text-primary" />,
                title: "Multi-Hospital Registry",
                desc: "Explore accredited medical branches and verified specialists.",
              },
              {
                icon: <ShieldCheck className="h-4 w-4 text-primary" />,
                title: "Digital Prescriptions",
                desc: "Official clinician diagnoses and downloadable PDF records.",
              },
              {
                icon: <Clock className="h-4 w-4 text-primary" />,
                title: "Clinical AI Guidance",
                desc: "Understand medications, dosage instructions, and schedules.",
              },
            ].map((feat) => (
              <div
                key={feat.title}
                className="surface-panel p-4 hover-lift flex flex-col justify-between bg-card/80 backdrop-blur-md"
              >
                <div className="flex items-center gap-2.5">
                  <span className="grid h-7 w-7 place-items-center rounded-lg bg-primary/10 text-primary">
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
          <div className="surface-panel p-6 sm:p-9 shadow-soft border border-border/80 bg-card/90 backdrop-blur-xl">
            {children}
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="mx-auto w-full max-w-6xl text-center text-xs text-muted-foreground pt-6 relative z-10">
        <p>© {new Date().getFullYear()} Medihub / CityCare Hospital Platform. All medical records encrypted & protected.</p>
      </footer>
    </div>
  );
}
