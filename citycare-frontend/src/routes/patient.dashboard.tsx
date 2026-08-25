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
  AlertCircle,
  CheckCircle2,
  Sparkles,
  MapPin,
  ChevronRight,
  ShieldCheck,
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  EmptyState,
  ErrorNote,
  LoadingRows,
  PageHeader,
  Panel,
  StatusBadge,
  AppointmentSkeleton,
  PrescriptionSkeleton,
} from "@/components/ui-kit";
import { formatDate, isCancelled, isUpcoming } from "@/lib/format";
import { useState } from "react";

export const Route = createFileRoute("/patient/dashboard")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Patient Workspace — Medihub / CityCare" },
      {
        name: "description",
        content: "View, manage and review your upcoming hospital appointments, medical prescriptions, and clinical history.",
      },
      { property: "og:title", content: "Patient Workspace — Medihub" },
      {
        property: "og:description",
        content: "Your upcoming visits, digital prescriptions and medical assistant in one calm view.",
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
  const [cancelModalId, setCancelModalId] = useState<string | number | null>(null);

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
      setCancelModalId(null);
      queryClient.invalidateQueries({ queryKey: ["appointments"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Could not cancel appointment");
      setCancelModalId(null);
    },
  });

  const all = query.data ?? [];
  const upcoming = all.filter((a) => isUpcoming(a) && !isCancelled(a));
  const past = all.filter((a) => !upcoming.includes(a));
  const nextAppointment = upcoming[0];
  const remainingUpcoming = upcoming.slice(1);

  return (
    <div className="space-y-8 max-w-6xl mx-auto pb-16">
      {/* Header with Call to Action */}
      <PageHeader
        eyebrow="Patient Portal"
        title={`Welcome back, ${user?.first_name ?? "Patient"}`}
        description="Review your upcoming medical appointments, download official doctor prescriptions, or schedule a specialist visit."
        action={
          <Button asChild size="lg" className="rounded-xl font-semibold shadow-soft tap-feedback">
            <Link to="/patient/book">
              <CalendarPlus className="mr-2 h-4 w-4" /> Book Consultation
            </Link>
          </Button>
        }
      />

      {/* Hero Next Appointment Spotlight */}
      {query.isLoading ? (
        <AppointmentSkeleton />
      ) : nextAppointment ? (
        <section className="surface-panel p-6 sm:p-8 bg-gradient-to-br from-card via-card to-primary-soft/30 border-primary/25 shadow-soft fade-rise relative overflow-hidden">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="space-y-3 min-w-0 max-w-2xl">
              <div className="inline-flex items-center gap-2 rounded-full bg-primary/15 px-3 py-1 text-xs font-semibold text-primary">
                <Sparkles className="h-3.5 w-3.5" />
                <span>Next Scheduled Consultation</span>
              </div>
              <h2 className="font-display text-xl sm:text-2xl font-bold tracking-tight text-foreground">
                {nextAppointment.doctor_name ? `Dr. ${nextAppointment.doctor_name}` : "Attending Specialist"}
              </h2>
              <div className="flex flex-wrap items-center gap-4 text-xs sm:text-sm text-muted-foreground font-medium">
                <span className="flex items-center gap-1.5 text-foreground font-semibold">
                  <CalendarDays className="h-4 w-4 text-primary" />
                  {formatDate(nextAppointment.date)}
                </span>
                <span>•</span>
                <span className="flex items-center gap-1.5 text-foreground font-semibold">
                  <Clock className="h-4 w-4 text-primary" />
                  Slot: {nextAppointment.slot}
                </span>
              </div>

              {nextAppointment.reason ? (
                <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed bg-surface/70 rounded-xl p-3 border border-border/50">
                  <strong className="text-foreground font-semibold">Reason for visit: </strong>
                  {nextAppointment.reason}
                </p>
              ) : null}
            </div>

            <div className="flex flex-col sm:flex-row md:flex-col items-stretch md:items-end gap-3 shrink-0">
              <StatusBadge status={nextAppointment.status ?? "booked"} />
              <Button
                variant="outline"
                size="sm"
                className="rounded-xl text-xs font-medium text-destructive border-destructive/25 hover:bg-destructive/10 hover:text-destructive tap-feedback"
                onClick={() => setCancelModalId(nextAppointment.id)}
              >
                <XCircle className="mr-1.5 h-3.5 w-3.5" /> Cancel Slot
              </Button>
            </div>
          </div>
        </section>
      ) : null}

      <div className="space-y-8">
        {/* Upcoming Consultations Grid (if > 1) */}
        {remainingUpcoming.length > 0 ? (
          <Panel
            title="Other Upcoming Consultations"
            description={`${remainingUpcoming.length} additional scheduled visit${remainingUpcoming.length === 1 ? "" : "s"}`}
          >
            <div className="grid gap-4 sm:grid-cols-2">
              {remainingUpcoming.map((appointment) => (
                <AppointmentCard
                  key={appointment.id}
                  appointment={appointment}
                  onCancel={() => setCancelModalId(appointment.id)}
                />
              ))}
            </div>
          </Panel>
        ) : null}

        {/* Empty State when no upcoming visits at all */}
        {!query.isLoading && upcoming.length === 0 ? (
          <Panel title="Upcoming Consultations">
            <EmptyState
              title="No upcoming consultations scheduled"
              description="Book an appointment with any verified specialist in the hospital network to see it listed here."
              action={
                <Button asChild className="rounded-xl font-semibold tap-feedback">
                  <Link to="/patient/book">Find Doctor & Book</Link>
                </Button>
              }
            />
          </Panel>
        ) : null}

        {/* Official Prescription Vault */}
        <Panel
          title="Digital Prescription Vault"
          description="Doctor-issued electronic diagnoses and signed medical records"
        >
          {prescriptions.isLoading ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <PrescriptionSkeleton />
              <PrescriptionSkeleton />
            </div>
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
              description="Digital prescriptions issued by attending physicians during consultations will appear here automatically."
              icon={<FileText className="h-6 w-6 opacity-60" />}
            />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {prescriptions.data?.map((prescription: Prescription) => (
                <div
                  key={prescription.id}
                  className="flex flex-col justify-between rounded-2xl border border-border/70 bg-card p-5 sm:p-6 shadow-subtle hover-lift"
                >
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="font-display text-base font-bold text-foreground leading-snug">
                        {prescription.diagnosis || "Clinical Consultation"}
                      </h4>
                      <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-0.5 text-[10px] font-semibold text-primary border border-primary/20">
                        <ShieldCheck className="h-3 w-3" /> Signed
                      </span>
                    </div>

                    <p className="text-xs text-muted-foreground flex items-center gap-1.5 font-medium">
                      <Stethoscope className="h-3.5 w-3.5 text-primary" />
                      <span>{prescription.doctor_name || "Attending Physician"}</span>
                      <span>•</span>
                      <span>{formatDate(prescription.created_at)}</span>
                    </p>

                    {prescription.medicines && prescription.medicines.length > 0 ? (
                      <div className="mt-3 space-y-1.5 rounded-xl bg-surface/70 p-3 text-xs border border-border/40">
                        <p className="font-semibold text-foreground/90 text-[11px] uppercase tracking-wider mb-1">
                          Prescribed Medication:
                        </p>
                        {prescription.medicines.map((m, idx) => (
                          <div key={idx} className="flex items-start gap-1.5 text-muted-foreground text-[11px]">
                            <span className="text-primary font-bold">•</span>
                            <span>
                              <strong className="text-foreground font-semibold">{m.name}</strong> ({m.dosage}) — {m.frequency} {m.duration ? `(${m.duration})` : ""}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : null}

                    {prescription.general_instructions ? (
                      <p className="text-xs text-muted-foreground italic bg-secondary/30 rounded-lg p-2">
                        "{prescription.general_instructions}"
                      </p>
                    ) : null}
                  </div>

                  {prescription.pdf_url ? (
                    <div className="mt-5 flex items-center gap-2.5 border-t border-border/50 pt-3.5">
                      <Button
                        asChild
                        size="sm"
                        variant="outline"
                        className="rounded-xl flex-1 text-xs font-semibold tap-feedback"
                      >
                        <a href={prescription.pdf_url} target="_blank" rel="noreferrer">
                          <ExternalLink className="mr-1.5 h-3.5 w-3.5 text-primary" /> View PDF
                        </a>
                      </Button>
                      <Button asChild size="sm" className="rounded-xl flex-1 text-xs font-semibold tap-feedback">
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

        {/* Consultation History */}
        {past.length > 0 ? (
          <Panel
            title="Consultation History"
            description="Past completed and cancelled medical appointments"
          >
            <div className="grid gap-4 sm:grid-cols-2">
              {past.map((appointment) => (
                <AppointmentCard key={appointment.id} appointment={appointment} muted />
              ))}
            </div>
          </Panel>
        ) : null}
      </div>

      {/* Cancellation Confirmation Dialog */}
      <Dialog open={Boolean(cancelModalId)} onOpenChange={(open) => !open && setCancelModalId(null)}>
        <DialogContent className="rounded-2xl sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="font-display text-lg font-bold">Cancel Consultation</DialogTitle>
            <DialogDescription className="text-sm text-muted-foreground">
              Are you sure you want to cancel this scheduled appointment? This time slot will be released back to the hospital booking calendar.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="mt-4 flex gap-2 sm:justify-end">
            <Button
              variant="outline"
              className="rounded-xl text-xs font-medium"
              onClick={() => setCancelModalId(null)}
            >
              Keep Appointment
            </Button>
            <Button
              variant="destructive"
              className="rounded-xl text-xs font-semibold tap-feedback"
              onClick={() => {
                if (cancelModalId) cancel.mutate(cancelModalId);
              }}
              disabled={cancel.isPending}
            >
              {cancel.isPending ? "Cancelling..." : "Confirm Cancellation"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function AppointmentCard({
  appointment,
  onCancel,
  muted,
}: {
  appointment: Appointment;
  onCancel?: () => void;
  muted?: boolean;
}) {
  const symptoms = appointment.symptoms ?? [];
  return (
    <article
      className={`rounded-2xl border border-border/70 bg-card p-5 shadow-subtle hover-lift flex flex-col justify-between ${
        muted ? "opacity-75 bg-surface/50" : ""
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
              <Clock className="h-3.5 w-3.5 text-primary/80" />
              <span>Time Slot: {appointment.slot}</span>
            </p>
          </div>
          <StatusBadge status={appointment.status ?? "booked"} />
        </div>

        {appointment.doctor_name ? (
          <p className="mt-3 text-xs font-semibold text-primary flex items-center gap-1.5">
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
            <span className="inline-flex items-center gap-1 rounded-full bg-secondary px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground border border-border/40">
              <Thermometer className="h-3 w-3 text-destructive" /> {appointment.temperature}°F
            </span>
          ) : null}
          {symptoms.map((symptom) => (
            <span
              key={symptom}
              className="rounded-full bg-secondary/80 px-2.5 py-0.5 text-[11px] font-medium capitalize text-muted-foreground border border-border/40"
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
          >
            <XCircle className="mr-1.5 h-3.5 w-3.5" />
            Cancel Appointment
          </Button>
        </div>
      ) : null}
    </article>
  );
}
