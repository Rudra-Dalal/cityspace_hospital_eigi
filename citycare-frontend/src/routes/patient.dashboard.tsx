import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, CalendarPlus, Clock, Thermometer } from "lucide-react";
import { toast } from "sonner";
import { appointmentsApi, asList, type Appointment } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { RoleGate } from "@/components/RoleGate";
import { Button } from "@/components/ui/button";
import {
  EmptyState,
  ErrorNote,
  LoadingRows,
  PageHeader,
  Panel,
  StatusBadge,
} from "@/components/ui-kit";
import { formatDate, isCancelled, isUpcoming } from "@/lib/format";

export const Route = createFileRoute("/patient/dashboard")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "My appointments — CityCare" },
      { name: "description", content: "View, manage and cancel your upcoming CityCare hospital appointments." },
      { property: "og:title", content: "My appointments — CityCare" },
      { property: "og:description", content: "Your upcoming visits, reasons and status in one calm view." },
    ],
  }),
  component: () => (
    <RoleGate role="customer">
      <PatientDashboard />
    </RoleGate>
  ),
});

function PatientDashboard() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["appointments", "my"],
    queryFn: async () => asList<Appointment>(await appointmentsApi.mine()),
  });

  const cancel = useMutation({
    mutationFn: (id: number | string) => appointmentsApi.cancel(id),
    onSuccess: () => {
      toast.success("Appointment cancelled");
      queryClient.invalidateQueries({ queryKey: ["appointments"] });
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not cancel"),
  });

  const all = query.data ?? [];
  const upcoming = all.filter((a) => isUpcoming(a) && !isCancelled(a));
  const past = all.filter((a) => !upcoming.includes(a));

  return (
    <>
      <PageHeader
        eyebrow={`Hello, ${user?.first_name ?? ""}`}
        title="Your appointments"
        description="Everything you've booked across the CityCare network, with the reason and symptoms you reported."
        action={
          <Button asChild size="lg" className="rounded-xl">
            <Link to="/patient/book">
              <CalendarPlus className="mr-2 h-4 w-4" /> Book appointment
            </Link>
          </Button>
        }
      />

      <div className="space-y-6">
        <Panel title="Upcoming" description={`${upcoming.length} scheduled visit${upcoming.length === 1 ? "" : "s"}`}>
          {query.isLoading ? (
            <LoadingRows />
          ) : query.isError ? (
            <ErrorNote message={query.error instanceof Error ? query.error.message : "Could not load appointments"} />
          ) : upcoming.length === 0 ? (
            <EmptyState
              title="No upcoming appointments"
              description="Book a slot in the next 7 days and it will appear here straight away."
              action={
                <Button asChild className="rounded-xl">
                  <Link to="/patient/book">Book appointment</Link>
                </Button>
              }
            />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {upcoming.map((appointment) => (
                <AppointmentCard
                  key={appointment.id}
                  appointment={appointment}
                  onCancel={() => cancel.mutate(appointment.id)}
                  cancelling={cancel.isPending && cancel.variables === appointment.id}
                />
              ))}
            </div>
          )}
        </Panel>

        {past.length > 0 ? (
          <Panel title="History" description="Past and cancelled appointments">
            <div className="grid gap-4 sm:grid-cols-2">
              {past.map((appointment) => (
                <AppointmentCard key={appointment.id} appointment={appointment} muted />
              ))}
            </div>
          </Panel>
        ) : null}
      </div>
    </>
  );
}

function AppointmentCard({
  appointment,
  onCancel,
  cancelling,
  muted,
}: {
  appointment: Appointment;
  onCancel?: () => void;
  cancelling?: boolean;
  muted?: boolean;
}) {
  const symptoms = appointment.symptoms ?? [];
  return (
    <article
      className={`hover-lift fade-rise rounded-2xl bg-surface p-5 ${muted ? "opacity-80" : ""}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2 font-display text-lg leading-tight">
            <CalendarDays className="h-4 w-4 shrink-0 text-primary" />
            {formatDate(appointment.date)}
          </p>
          <p className="mt-1.5 flex items-center gap-2 text-sm text-muted-foreground">
            <Clock className="h-3.5 w-3.5" /> {appointment.slot}
          </p>
        </div>
        <StatusBadge status={appointment.status ?? "booked"} />
      </div>

      {appointment.reason ? (
        <p className="mt-4 text-sm text-foreground/90">{appointment.reason}</p>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {appointment.temperature ? (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-card px-2.5 py-1 text-xs font-medium text-muted-foreground">
            <Thermometer className="h-3 w-3" /> {appointment.temperature}°
          </span>
        ) : null}
        {symptoms.map((symptom) => (
          <span
            key={symptom}
            className="rounded-full bg-card px-2.5 py-1 text-xs font-medium capitalize text-muted-foreground"
          >
            {symptom}
          </span>
        ))}
      </div>

      {onCancel ? (
        <Button
          variant="ghost"
          size="sm"
          className="mt-4 rounded-xl text-destructive hover:bg-destructive/10 hover:text-destructive"
          onClick={onCancel}
          disabled={cancelling}
        >
          {cancelling ? "Cancelling…" : "Cancel appointment"}
        </Button>
      ) : null}
    </article>
  );
}
