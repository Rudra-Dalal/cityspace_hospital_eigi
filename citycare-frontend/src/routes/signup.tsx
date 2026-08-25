import { useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { CheckCircle2, Loader2, ArrowRight, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { authApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field, fieldErrorClass, fieldInputClass } from "@/components/Field";
import { ErrorNote } from "@/components/ui-kit";
import { cn } from "@/lib/utils";
import { AuthLayout } from "./index";

export const Route = createFileRoute("/signup")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Register Patient Account — Medihub / CityCare" },
      {
        name: "description",
        content:
          "Register as a Medihub patient to schedule doctor appointments and access digital medical records.",
      },
      { property: "og:title", content: "Register Patient Account — Medihub" },
      {
        property: "og:description",
        content: "Register in under a minute and book your first specialist consultation.",
      },
    ],
  }),
  component: SignupPage,
});

type Errors = Partial<Record<"first_name" | "last_name" | "email" | "mobile" | "password", string>>;

function SignupPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    email: "",
    mobile: "",
    password: "",
  });
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  function update(key: keyof typeof form, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const next: Errors = {};
    if (form.first_name.trim().length < 2) next.first_name = "Enter your first name";
    if (form.last_name.trim().length < 2) next.last_name = "Enter your last name";
    if (!/^\S+@\S+\.\S+$/.test(form.email.trim())) next.email = "Enter a valid email address";

    const rawMobile = form.mobile.replace(/[\s\-\.\(\)]/g, "");
    const normalizedMobile = rawMobile.startsWith("+91")
      ? rawMobile
      : rawMobile.length === 10
        ? `+91${rawMobile}`
        : form.mobile.trim();

    if (!/^\+91[6-9]\d{9}$/.test(normalizedMobile)) {
      next.mobile = "Enter a valid 10-digit mobile number (e.g. +91 98765 43210 or 9876543210)";
    }
    if (form.password.length < 6) next.password = "Password must be at least 6 characters";
    setErrors(next);
    setFormError("");
    if (Object.keys(next).length) return;

    setSubmitting(true);
    try {
      await authApi.signup({
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        email: form.email.trim(),
        mobile: normalizedMobile,
        password: form.password,
      });
      setDone(true);
      toast.success("Account created successfully! Redirecting to sign in…");
      setTimeout(() => navigate({ to: "/" }), 1200);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Unable to create your account");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Your unified personal healthcare workspace."
      subtitle="Register as a patient to schedule doctor visits, review consultation history, and download authenticated medical prescriptions."
    >
      {done ? (
        <div className="py-8 text-center space-y-4 fade-rise">
          <div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-success/15 text-success shadow-subtle border border-success/20">
            <CheckCircle2 className="h-10 w-10" />
          </div>
          <h2 className="font-display text-2xl font-bold tracking-tight text-foreground">
            Welcome to Medihub!
          </h2>
          <p className="text-xs sm:text-sm text-muted-foreground">
            Your patient account has been verified. Redirecting to sign in…
          </p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <div>
            <h2 className="font-display text-2xl font-bold tracking-tight text-foreground">
              Create Patient Account
            </h2>
            <p className="mt-1 text-xs sm:text-sm text-muted-foreground">
              Join the Medihub clinical network in under a minute to book specialist visits.
            </p>
          </div>

          {formError ? <ErrorNote message={formError} /> : null}

          <div className="grid gap-3 sm:grid-cols-2">
            <Field id="first_name" label="First Name" error={errors.first_name}>
              <Input
                id="first_name"
                autoComplete="given-name"
                placeholder="Jane"
                value={form.first_name}
                onChange={(e) => update("first_name", e.target.value)}
                className={cn(
                  fieldInputClass,
                  errors.first_name && fieldErrorClass,
                  "rounded-xl h-11 text-sm",
                )}
              />
            </Field>

            <Field id="last_name" label="Last Name" error={errors.last_name}>
              <Input
                id="last_name"
                autoComplete="family-name"
                placeholder="Doe"
                value={form.last_name}
                onChange={(e) => update("last_name", e.target.value)}
                className={cn(
                  fieldInputClass,
                  errors.last_name && fieldErrorClass,
                  "rounded-xl h-11 text-sm",
                )}
              />
            </Field>
          </div>

          <Field id="email" label="Email Address" error={errors.email}>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="jane@example.com"
              value={form.email}
              onChange={(e) => update("email", e.target.value)}
              className={cn(fieldInputClass, errors.email && fieldErrorClass, "rounded-xl h-11 text-sm")}
            />
          </Field>

          <Field id="mobile" label="Mobile Phone" error={errors.mobile}>
            <Input
              id="mobile"
              type="tel"
              autoComplete="tel"
              placeholder="+91 98765 43210"
              value={form.mobile}
              onChange={(e) => update("mobile", e.target.value)}
              className={cn(fieldInputClass, errors.mobile && fieldErrorClass, "rounded-xl h-11 text-sm")}
            />
          </Field>

          <Field id="password" label="Password (min 6 characters)" error={errors.password}>
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              placeholder="••••••••"
              value={form.password}
              onChange={(e) => update("password", e.target.value)}
              className={cn(fieldInputClass, errors.password && fieldErrorClass, "rounded-xl h-11 text-sm")}
            />
          </Field>

          <Button
            type="submit"
            size="lg"
            className="w-full rounded-xl font-bold shadow-soft tap-feedback h-11 mt-2"
            disabled={submitting}
          >
            {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Complete Registration
          </Button>

          <div className="pt-2 text-center border-t border-border/50">
            <p className="text-xs sm:text-sm text-muted-foreground">
              Already have an account?{" "}
              <Link
                to="/"
                className="font-semibold text-primary underline-offset-4 hover:underline transition-colors tap-feedback"
              >
                Sign in
              </Link>
            </p>
          </div>
        </form>
      )}
    </AuthLayout>
  );
}
