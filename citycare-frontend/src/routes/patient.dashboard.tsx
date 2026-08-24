import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarDays,
  CalendarPlus,
  Clock,
  Thermometer,
  FileText,
  Download,
  ExternalLink,
  User,
  Stethoscope,
  XCircle,
  Building2,
} from "lucide-react";
import { toast } from "sonner";
import {
  appointmentsApi,
  asList,
  prescriptionsApi,
  type Appointment,
  type Prescription,
} from "@/lib/api";
import { PatientPrescriptionChat } from "@/components/ai/PatientPrescriptionChat";
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
      {
        name: "description",
        content: "View, manage and cancel your upcoming CityCare hospital appointments.",
      },
      { property: "og:title", content: "My appointments — CityCare" },
      {
        property: "og:description",
        content: "Your upcoming visits, reasons and status in one calm view.",
      },
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

  const prescriptions = useQuery({
    queryKey: ["prescriptions", "my"],
    queryFn: () => prescriptionsApi.mine(),
  });

  const cancel = useMutation({
    mutationFn: (id: number | string) => appointmentsApi.cancel(id),
    onSuccess: () => {
      toast.success("Appointment successfully cancelled");
      queryClient.invalidateQueries({ queryKey: ["appointments"] });
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : "Could not cancel appointment"),
  });

  const all = query.data ?? [];
  const upcoming = all.filter((a) => isUpcoming(a) && !isCancelled(a));
  const past = all.filter((a) => !upcoming.includes(a));

  return (
    <div className="space-y-8 max-w-6xl mx-auto pb-12">
      <PageHeader
        eyebrow={`Patient Portal`}
        title={`Welcome back, ${user?.first_name ?? "Patient"}`}
        description="Review your upcoming medical appointments, download official doctor prescriptions, or schedule a specialist visit."
        action={
          <Button asChild size="lg" className="rounded-xl font-semibold shadow-soft tap-feedback">
            <Link to="/patient/book">
              <CalendarPlus className="mr-2 h-4 w-4" /> Book New Consultation
            </Link>
          </Button>
        }
      />

      <div className="space-y-8">
        {/* Upcoming Consultations */}
        <Panel
          title="Upcoming Consultations"
          description={`${upcoming.length} scheduled visit${upcoming.length === 1 ? "" : "s"} across the CityCare network`}
        >
          {query.isLoading ? (
            <LoadingRows rows={2} />
          ) : query.isError ? (
            <ErrorNote
              message={
                query.error instanceof Error ? query.error.message : "Could not load appointments"
              }
              onRetry={() => query.refetch()}
            />
          ) : upcoming.length === 0 ? (
            <EmptyState
              title="No upcoming consultations scheduled"
              description="Book an appointment with any verified specialist in the network to see it listed here."
              action={
                <Button asChild className="rounded-xl font-semibold tap-feedback">
                  <Link to="/patient/book">Book Consultation</Link>
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

        {/* Prescription Vault */}
        <Panel
          title="Official Prescriptions"
          description="Doctor-issued digital prescriptions and medical records"
        >
          {prescriptions.isLoading ? (
            <LoadingRows rows={2} />
          ) : prescriptions.isError ? (
            <ErrorNote
              message={
                prescriptions.error instanceof Error
                  ? prescriptions.error.message
                  : "Could not load prescriptions"
              }
              onRetry={() => prescriptions.refetch()}
            />
          ) : (prescriptions.data || []).length === 0 ? (
            <EmptyState
              title="No prescriptions on record"
              description="Prescriptions issued by attending physicians during consultations will be stored here."
              icon={<FileText className="h-6 w-6 opacity-60" />}
            />
          ) : (
            <div className="grid gap-3.5 sm:grid-cols-2">
              {prescriptions.data?.map((prescription: Prescription) => (
                <div
                  key={prescription.id}
                  className="flex flex-col justify-between rounded-2xl border border-border/70 bg-card p-5 shadow-subtle hover-lift"
                >
                  <div className="space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="font-bold text-base text-foreground leading-snug">
                        {prescription.diagnosis || "Medical Consultation"}
                      </h4>
                      <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-0.5 text-[10px] font-bold text-primary">
                        Issued
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground flex items-center gap-1.5">
                      <Stethoscope className="h-3.5 w-3.5 text-primary" />
                      <span>{prescription.doctor_name || "Specialist Physician"}</span>
                      <span>•</span>
                      <span>{formatDate(prescription.created_at)}</span>
                    </p>
                    {prescription.medicines && prescription.medicines.length > 0 ? (
                      <div className="mt-3 space-y-1 rounded-xl bg-surface p-3 text-xs">
                        <p className="font-semibold text-foreground/80 mb-1">
                          Prescribed Medicines:
                        </p>
                        {prescription.medicines.map((m, idx) => (
                          <p key={idx} className="text-muted-foreground text-[11px]">
                            • <strong className="text-foreground">{m.name}</strong> ({m.dosage}) -{" "}
                            {m.frequency}
                          </p>
                        ))}
                      </div>
                    ) : null}
                  </div>

                  {prescription.pdf_url ? (
                    <div className="mt-4 flex items-center gap-2 border-t border-border/50 pt-3">
                      <Button
                        asChild
                        size="sm"
                        variant="outline"
                        className="rounded-xl flex-1 text-xs tap-feedback"
                      >
                        <a href={prescription.pdf_url} target="_blank" rel="noreferrer">
                          <ExternalLink className="mr-1.5 h-3.5 w-3.5" /> View PDF
                        </a>
                      </Button>
                      <Button asChild size="sm" className="rounded-xl flex-1 text-xs tap-feedback">
                        <a href={prescription.pdf_url} download>
                          <Download className="mr-1.5 h-3.5 w-3.5" /> Download
                        </a>
                      </Button>
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </Panel>

        {/* AI Health & Prescription Assistant */}
        <PatientPrescriptionChat />

        {/* Past Consultation History */}
        {past.length > 0 ? (
          <Panel
            title="Consultation History"
            description="Past completed and cancelled appointments"
          >
            <div className="grid gap-4 sm:grid-cols-2">
              {past.map((appointment) => (
                <AppointmentCard key={appointment.id} appointment={appointment} muted />
              ))}
            </div>
          </Panel>
        ) : null}
      </div>
    </div>
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
      className={`rounded-2xl border border-border/70 bg-card p-5 shadow-subtle hover-lift flex flex-col justify-between ${
        muted ? "opacity-75 bg-surface/40" : ""
      }`}
    >
      <div>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="flex items-center gap-2 font-display text-base font-bold leading-tight text-foreground">
              <CalendarDays className="h-4 w-4 shrink-0 text-primary" />
              {formatDate(appointment.date)}
            </p>
            <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground font-medium">
              <Clock className="h-3.5 w-3.5 text-primary/70" />
              <span>Time Slot: {appointment.slot}</span>
            </p>
          </div>
          <StatusBadge status={appointment.status ?? "booked"} />
        </div>

        {appointment.doctor_name ? (
          <p className="mt-3 text-xs font-semibold text-primary flex items-center gap-1">
            <Stethoscope className="h-3.5 w-3.5" />
            <span>Dr. {appointment.doctor_name}</span>
          </p>
        ) : null}

        {appointment.reason ? (
          <p className="mt-3 text-xs text-foreground/90 leading-relaxed bg-surface/70 rounded-xl p-3 border border-border/40">
            {appointment.reason}
          </p>
        ) : null}

        <div className="mt-3.5 flex flex-wrap items-center gap-1.5">
          {appointment.temperature ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-secondary px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground">
              <Thermometer className="h-3 w-3 text-destructive" /> {appointment.temperature}°F
            </span>
          ) : null}
          {symptoms.map((symptom) => (
            <span
              key={symptom}
              className="rounded-full bg-secondary/80 px-2.5 py-0.5 text-[11px] font-medium capitalize text-muted-foreground"
            >
              {symptom}
            </span>
          ))}
        </div>
      </div>

      {onCancel ? (
        <div className="mt-4 border-t border-border/50 pt-3">
          <Button
            variant="ghost"
            size="sm"
            className="w-full rounded-xl text-xs font-semibold text-destructive hover:bg-destructive/10 hover:text-destructive tap-feedback"
            onClick={onCancel}
            disabled={cancelling}
          >
            <XCircle className="mr-1.5 h-3.5 w-3.5" />
            {cancelling ? "Cancelling Slot…" : "Cancel Appointment"}
          </Button>
        </div>
      ) : null}
    </article>
  );
}
