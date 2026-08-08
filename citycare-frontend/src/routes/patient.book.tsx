import { useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, TriangleAlert } from "lucide-react";
import { toast } from "sonner";
import { appointmentsApi } from "@/lib/api";
import { RoleGate } from "@/components/RoleGate";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field, fieldErrorClass, fieldInputClass } from "@/components/Field";
import { EmptyState, ErrorNote, PageHeader, Panel } from "@/components/ui-kit";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { formatDate, nextDays, toDateKey } from "@/lib/format";

const SYMPTOMS = ["fever", "cough", "cold", "bodyache", "headache", "other"] as const;

export const Route = createFileRoute("/patient/book")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Book an appointment — CityCare" },
      {
        name: "description",
        content: "Pick a day in the next week, choose a free slot and tell your care team what's going on.",
      },
      { property: "og:title", content: "Book an appointment — CityCare" },
      { property: "og:description", content: "Live free slots across a 7-day booking window." },
    ],
  }),
  component: () => (
    <RoleGate role="customer">
      <BookAppointment />
    </RoleGate>
  ),
});

function BookAppointment() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const days = nextDays(7);
  const [date, setDate] = useState(toDateKey(days[0]!));
  const [slot, setSlot] = useState<string | null>(null);
  const [symptoms, setSymptoms] = useState<string[]>([]);
  const [temperature, setTemperature] = useState("");
  const [reason, setReason] = useState("");
  const [errors, setErrors] = useState<{ slot?: string; reason?: string; temperature?: string; symptoms?: string }>({});
  const [conflict, setConflict] = useState("");
  const [success, setSuccess] = useState<{ date: string; slot: string } | null>(null);

  const slotsQuery = useQuery({
    queryKey: ["free-slots", date],
    queryFn: async () => {
      const data = await appointmentsApi.freeSlots(date);
      return Array.isArray(data?.free_slots) ? data.free_slots : [];
    },
  });

  const book = useMutation({
    mutationFn: (payload: {
      date: string;
      slot: string;
      reason: string;
      temperature: number;
      symptoms: string[];
    }) => appointmentsApi.create(payload),
    onSuccess: (_data, variables) => {
      setSuccess({ date: variables.date, slot: variables.slot });
      setConflict("");
      setSlot(null);
      toast.success("Appointment booked");
      queryClient.invalidateQueries({ queryKey: ["appointments"] });
      queryClient.invalidateQueries({ queryKey: ["free-slots", variables.date] });
    },
    onError: (error) => {
      setConflict(error instanceof Error ? error.message : "Could not book this slot");
      queryClient.invalidateQueries({ queryKey: ["free-slots", date] });
    },
  });

  function toggleSymptom(value: string) {
    setSymptoms((prev) => (prev.includes(value) ? prev.filter((s) => s !== value) : [...prev, value]));
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const next: { slot?: string; reason?: string; temperature?: string; symptoms?: string } = {};
    if (!slot) next.slot = "Choose a free slot";
    if (reason.trim().length < 5) next.reason = "Tell us a little more (min 5 characters)";
    const temp = Number(temperature);
    if (!temperature.trim() || Number.isNaN(temp) || temp < 90 || temp > 115) {
      next.temperature = "Enter a temperature in °F between 90 and 115";
    }
    if (symptoms.length === 0) next.symptoms = "Select at least one symptom";
    setErrors(next);
    setConflict("");
    if (Object.keys(next).length) return;

    book.mutate({ date, slot: slot!, reason: reason.trim(), temperature: temp, symptoms });
  }

  if (success) {
    return (
      <>
        <PageHeader eyebrow="Confirmed" title="Your appointment is booked" />
        <Panel className="mx-auto max-w-xl text-center">
          <CheckCircle2 className="mx-auto h-12 w-12 text-success" />
          <p className="mt-5 font-display text-2xl leading-tight">{formatDate(success.date)}</p>
          <p className="mt-1 text-sm text-muted-foreground">Slot {success.slot}</p>
          <div className="mt-7 flex flex-wrap justify-center gap-3">
            <Button className="rounded-xl" onClick={() => navigate({ to: "/patient/dashboard" })}>
              View my appointments
            </Button>
            <Button
              variant="outline"
              className="rounded-xl"
              onClick={() => {
                setSuccess(null);
                setReason("");
                setTemperature("");
                setSymptoms([]);
              }}
            >
              Book another
            </Button>
          </div>
        </Panel>
      </>
    );
  }

  return (
    <>
      <PageHeader
        eyebrow="New appointment"
        title="Book a visit"
        description="Slots open on a rolling 7-day window. Pick a day to see what's still free."
      />

      <form onSubmit={handleSubmit} className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]" noValidate>
        <div className="space-y-6">
          <Panel title="Choose a day">
            <div className="grid grid-cols-3 gap-2.5 sm:grid-cols-4 lg:grid-cols-7">
              {days.map((day, index) => {
                const key = toDateKey(day);
                const active = key === date;
                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => {
                      setDate(key);
                      setSlot(null);
                      setConflict("");
                    }}
                    className={cn(
                      "rounded-xl px-2 py-3 text-center transition-all duration-200",
                      active
                        ? "bg-primary text-primary-foreground shadow-soft"
                        : "bg-surface text-foreground hover:-translate-y-0.5 hover:bg-accent",
                    )}
                  >
                    <span className="block text-[11px] font-semibold uppercase tracking-wide opacity-75">
                      {index === 0 ? "Today" : day.toLocaleDateString(undefined, { weekday: "short" })}
                    </span>
                    <span className="mt-1 block font-display text-lg leading-none">{day.getDate()}</span>
                    <span className="mt-1 block text-[11px] opacity-70">
                      {day.toLocaleDateString(undefined, { month: "short" })}
                    </span>
                  </button>
                );
              })}
            </div>
          </Panel>

          <Panel title="Available slots" description={formatDate(date)}>
            {slotsQuery.isLoading ? (
              <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 rounded-xl" />
                ))}
              </div>
            ) : slotsQuery.isError ? (
              <ErrorNote
                message={slotsQuery.error instanceof Error ? slotsQuery.error.message : "Could not load slots"}
              />
            ) : (slotsQuery.data ?? []).length === 0 ? (
              <EmptyState title="No free slots on this day" description="Try another day in the window." />
            ) : (
              <>
                <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
                  {(slotsQuery.data ?? []).map((value) => {
                    const active = value === slot;
                    return (
                      <button
                        key={value}
                        type="button"
                        onClick={() => setSlot(value)}
                        className={cn(
                          "rounded-xl px-3 py-3 text-sm font-semibold transition-all duration-200",
                          active
                            ? "bg-primary text-primary-foreground shadow-soft scale-[1.02]"
                            : "bg-surface hover:-translate-y-0.5 hover:bg-accent",
                        )}
                      >
                        {value}
                      </button>
                    );
                  })}
                </div>
                {errors.slot ? <p className="mt-3 text-xs font-medium text-destructive">{errors.slot}</p> : null}
              </>
            )}
          </Panel>
        </div>

        <div className="space-y-6">
          <Panel title="How are you feeling?">
            <div className="space-y-5">
              <div className="space-y-2">
                <p className="text-sm font-medium">Symptoms</p>
                <div className="flex flex-wrap gap-2">
                  {SYMPTOMS.map((symptom) => {
                    const active = symptoms.includes(symptom);
                    return (
                      <button
                        key={symptom}
                        type="button"
                        onClick={() => toggleSymptom(symptom)}
                        className={cn(
                          "rounded-full px-4 py-2 text-sm font-medium capitalize transition-all duration-200",
                          active
                            ? "bg-primary text-primary-foreground shadow-soft"
                            : "bg-surface text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                        )}
                      >
                        {symptom}
                      </button>
                    );
                  })}
                </div>
                {errors.symptoms ? (
                  <p className="text-xs font-medium text-destructive">{errors.symptoms}</p>
                ) : null}
              </div>

              <Field id="temperature" label="Temperature (°F)" error={errors.temperature}>
                <Input
                  id="temperature"
                  inputMode="decimal"
                  placeholder="98.6"
                  value={temperature}
                  onChange={(e) => setTemperature(e.target.value)}
                  className={cn(fieldInputClass, errors.temperature && fieldErrorClass)}
                />
              </Field>

              <Field id="reason" label="Reason for visit" error={errors.reason}>
                <Textarea
                  id="reason"
                  rows={4}
                  placeholder="Describe what's bothering you…"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  maxLength={1000}
                  className={cn(
                    "rounded-xl border-border bg-background",
                    errors.reason && fieldErrorClass,
                  )}
                />
              </Field>
            </div>
          </Panel>

          {conflict ? (
            <div className="flex items-start gap-3 rounded-2xl bg-warning/15 px-4 py-3.5 text-sm font-medium text-warning-foreground">
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{conflict}</span>
            </div>
          ) : null}

          <Button type="submit" size="lg" className="w-full rounded-xl" disabled={book.isPending}>
            {book.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Confirm appointment
          </Button>
        </div>
      </form>
    </>
  );
}
