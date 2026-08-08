import { useState } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { CheckCircle2, Loader2 } from "lucide-react";
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
      { title: "Create your patient account — CityCare" },
      {
        name: "description",
        content: "Register as a CityCare patient to book appointments with hospitals across the network.",
      },
      { property: "og:title", content: "Create your patient account — CityCare" },
      {
        property: "og:description",
        content: "Register in under a minute and book your first appointment.",
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
    if (!/^[0-9+\-\s()]{7,15}$/.test(form.mobile.trim())) next.mobile = "Enter a valid mobile number";
    if (form.password.length < 6) next.password = "Use at least 6 characters";
    setErrors(next);
    setFormError("");
    if (Object.keys(next).length) return;

    setSubmitting(true);
    try {
      await authApi.signup({
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        email: form.email.trim(),
        mobile: form.mobile.trim(),
        password: form.password,
      });
      setDone(true);
      toast.success("Account created — you can sign in now.");
      setTimeout(() => navigate({ to: "/" }), 1200);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Unable to create your account");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Your care history, finally in one place"
      subtitle="Create a patient account to book appointments, track symptoms you reported and cancel when plans change."
    >
      {done ? (
        <div className="py-6 text-center">
          <CheckCircle2 className="mx-auto h-10 w-10 text-success" />
          <h2 className="mt-4 font-display text-2xl">You're all set</h2>
          <p className="mt-2 text-sm text-muted-foreground">Taking you to sign in…</p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-5" noValidate>
          <div>
            <h2 className="font-display text-2xl leading-tight">Create your account</h2>
            <p className="mt-1 text-sm text-muted-foreground">Patients register here in under a minute.</p>
          </div>

          {formError ? <ErrorNote message={formError} /> : null}

          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="first_name" label="First name" error={errors.first_name}>
              <Input
                id="first_name"
                value={form.first_name}
                onChange={(e) => update("first_name", e.target.value)}
                className={cn(fieldInputClass, errors.first_name && fieldErrorClass)}
              />
            </Field>
            <Field id="last_name" label="Last name" error={errors.last_name}>
              <Input
                id="last_name"
                value={form.last_name}
                onChange={(e) => update("last_name", e.target.value)}
                className={cn(fieldInputClass, errors.last_name && fieldErrorClass)}
              />
            </Field>
          </div>

          <Field id="email" label="Email" error={errors.email}>
            <Input
              id="email"
              type="email"
              value={form.email}
              onChange={(e) => update("email", e.target.value)}
              className={cn(fieldInputClass, errors.email && fieldErrorClass)}
            />
          </Field>

          <Field id="mobile" label="Mobile" error={errors.mobile}>
            <Input
              id="mobile"
              inputMode="tel"
              value={form.mobile}
              onChange={(e) => update("mobile", e.target.value)}
              className={cn(fieldInputClass, errors.mobile && fieldErrorClass)}
            />
          </Field>

          <Field id="password" label="Password" error={errors.password} hint="At least 6 characters.">
            <Input
              id="password"
              type="password"
              value={form.password}
              onChange={(e) => update("password", e.target.value)}
              className={cn(fieldInputClass, errors.password && fieldErrorClass)}
            />
          </Field>

          <Button type="submit" size="lg" className="w-full rounded-xl" disabled={submitting}>
            {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Create account
          </Button>

          <p className="text-center text-sm text-muted-foreground">
            Already registered?{" "}
            <Link to="/" className="font-semibold text-primary underline-offset-4 hover:underline">
              Sign in
            </Link>
          </p>
        </form>
      )}
    </AuthLayout>
  );
}
