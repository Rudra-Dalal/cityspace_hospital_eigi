import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarCheck,
  CalendarDays,
  Clock,
  Mail,
  Phone,
  Users,
  CheckCircle2,
  FileEdit,
  Stethoscope,
  Building2,
  Thermometer,
  User,
} from "lucide-react";
import { toast } from "sonner";
import { appointmentsApi, asList, doctorApi, type Appointment } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { PrescriptionForm } from "@/components/prescriptions/PrescriptionForm";
import { useAuth } from "@/lib/auth";
import { RoleGate } from "@/components/RoleGate";
import {
  EmptyState,
  ErrorNote,
  LoadingRows,
  PageHeader,
  Panel,
  StatCard,
  StatusBadge,
} from "@/components/ui-kit";
import { formatDate, isToday, personName } from "@/lib/format";
import { DoctorAIChat } from "@/components/ai/DoctorAIChat";

export const Route = createFileRoute("/doctor/dashboard")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Doctor schedule — CityCare" },
      {
        name: "description",
        content: "Your CityCare consulting schedule, appointment volume and profile details.",
      },
      { property: "og:title", content: "Doctor schedule — CityCare" },
      { property: "og:description", content: "Today's clinic at a glance, plus the week ahead." },
    ],
  }),
  component: () => (
    <RoleGate role="doctor">
      <DoctorDashboard />
    </RoleGate>
  ),
});

function DoctorDashboard() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [prescribing, setPrescribing] = useState<string | null>(null);

  const info = useQuery({ queryKey: ["doctor", "info"], queryFn: () => doctorApi.info() });
  const stats = useQuery({ queryKey: ["doctor", "stats"], queryFn: () => doctorApi.stats() });
  const schedule = useQuery({
    queryKey: ["doctor", "schedule"],
    queryFn: async () => asList<Appointment>(await doctorApi.schedule()),
  });

  const appointments = schedule.data ?? [];
  const accept = useMutation({
    mutationFn: (id: string | number) => appointmentsApi.accept(id),
    onSuccess: () => {
      toast.success("Appointment accepted");
      queryClient.invalidateQueries({ queryKey: ["doctor", "schedule"] });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Could not accept appointment"),
  });

  const today = appointments.filter((a) => isToday(a.date));
  const upcoming = appointments.filter((a) => !isToday(a.date));
  const statsData = stats.data;
  const profile = (info.data ?? {}) as Record<string, unknown>;

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12">
      <PageHeader
        eyebrow="Clinical Workspace"
        title={`Dr. ${personName(user, "Clinician")}`}
        description="Review patient consultations, issue digital prescriptions, and query your AI schedule assistant."
      />

      {/* Metric Stat Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Today's Consultations"
          value={statsData ? ((statsData["today_visits"] as number) ?? today.length) : today.length}
          icon={<CalendarCheck className="h-4 w-4" />}
          hint="Scheduled for today"
        />
        <StatCard
          label="Upcoming Visits"
          value={
            statsData
              ? ((statsData["upcoming_visits"] as number) ?? upcoming.length)
              : upcoming.length
          }
          icon={<CalendarDays className="h-4 w-4" />}
          hint="Next 7 days"
        />
        <StatCard
          label="Total Consultations"
          value={
            statsData
              ? ((statsData["total_patients"] as number) ?? appointments.length)
              : appointments.length
          }
          icon={<Users className="h-4 w-4" />}
          hint="All time recorded"
        />
        <StatCard
          label="Weekly Total"
          value={appointments.length}
          icon={<Clock className="h-4 w-4" />}
          hint="Active appointment volume"
        />
      </div>

      {/* Main Schedule & AI Grid */}
      <div className="grid gap-8 lg:grid-cols-[1.4fr_0.6fr]">
        <div className="space-y-8">
          {/* Today's Queue */}
          <Panel
            title="Today's Consultation Queue"
            description={formatDate(new Date().toISOString().slice(0, 10))}
          >
            {schedule.isLoading ? (
              <LoadingRows rows={2} />
            ) : schedule.isError ? (
              <ErrorNote
                message={
                  schedule.error instanceof Error
                    ? schedule.error.message
                    : "Could not load schedule"
                }
                onRetry={() => schedule.refetch()}
              />
            ) : today.length === 0 ? (
              <EmptyState
                title="No consultations today"
                description="Your clinic queue for today is clear. Upcoming bookings will appear here."
              />
            ) : (
              <div className="space-y-4">
                {today.map((appointment) => (
                  <div key={appointment.id} className="space-y-3">
                    <DoctorAppointmentItem
                      appointment={appointment}
                      onAccept={() => accept.mutate(appointment.id)}
                      accepting={accept.isPending && accept.variables === appointment.id}
                      onPrescribe={() =>
                        setPrescribing((curr) =>
                          curr === String(appointment.id) ? null : String(appointment.id),
                        )
                      }
                      isPrescribing={prescribing === String(appointment.id)}
                    />
                    {prescribing === String(appointment.id) ? (
                      <PrescriptionForm
                        appointmentId={String(appointment.id)}
                        onDone={() => setPrescribing(null)}
                      />
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </Panel>

          {/* Upcoming Schedule */}
          {upcoming.length > 0 ? (
            <Panel title="Upcoming Schedule" description="Bookings in the upcoming days">
              <div className="space-y-3">
                {upcoming.map((appointment) => (
                  <DoctorAppointmentItem key={appointment.id} appointment={appointment} />
                ))}
              </div>
            </Panel>
          ) : null}
        </div>

        {/* Right Sidebar: Profile & AI Chat */}
        <div className="space-y-6">
          {/* Physician Profile Card */}
          <Panel title="Physician Profile">
            <div className="space-y-3 text-xs">
              <div className="flex items-center gap-3 border-b border-border/50 pb-3">
                <span className="grid h-10 w-10 place-items-center rounded-2xl bg-primary/10 text-sm font-bold text-primary">
                  {user?.first_name?.[0]}
                  {user?.last_name?.[0]}
                </span>
                <div>
                  <p className="font-bold text-sm text-foreground">
                    Dr. {user?.first_name} {user?.last_name}
                  </p>
                  <p className="text-primary font-semibold">
                    {String(
                      profile["specialization"] || user?.specialization || "General Medicine",
                    )}
                  </p>
                </div>
              </div>

              {profile["qualification"] || user?.qualification ? (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Qualification:</span>
                  <span className="font-medium text-foreground">
                    {String(profile["qualification"] || user?.qualification)}
                  </span>
                </div>
              ) : null}

              {profile["working_hours"] || user?.working_hours ? (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Hours:</span>
                  <span className="font-medium text-foreground">
                    {String(profile["working_hours"] || user?.working_hours)}
                  </span>
                </div>
              ) : null}

              {user?.email ? (
                <div className="flex items-center gap-2 text-muted-foreground pt-1">
                  <Mail className="h-3.5 w-3.5" />
                  <span className="truncate">{user.email}</span>
                </div>
              ) : null}
            </div>
          </Panel>

          {/* Clinical Assistant AI */}
          <DoctorAIChat />
        </div>
      </div>
    </div>
  );
}

function DoctorAppointmentItem({
  appointment,
  onAccept,
  accepting,
  onPrescribe,
  isPrescribing,
}: {
  appointment: Appointment;
  onAccept?: () => void;
  accepting?: boolean;
  onPrescribe?: () => void;
  isPrescribing?: boolean;
}) {
  const isBooked = (appointment.status ?? "").toLowerCase() === "booked";
  const isAccepted = (appointment.status ?? "").toLowerCase() === "accepted";
  const patient = appointment.customer || {};
  const patientName =
    appointment.patient_name ||
    `${patient.first_name || ""} ${patient.last_name || ""}`.trim() ||
    "Patient";
  const symptoms = appointment.symptoms ?? [];

  return (
    <div className="rounded-2xl border border-border/70 bg-card p-5 shadow-subtle hover-lift flex flex-col justify-between space-y-4">
      <div>
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="grid h-7 w-7 place-items-center rounded-full bg-secondary text-foreground text-xs font-bold">
                <User className="h-4 w-4 text-primary" />
              </span>
              <h4 className="font-display font-bold text-base text-foreground leading-tight">
                {patientName}
              </h4>
            </div>

            <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              <span className="flex items-center gap-1 font-semibold text-foreground">
                <CalendarDays className="h-3.5 w-3.5 text-primary" />
                {formatDate(appointment.date)}
              </span>
              <span className="flex items-center gap-1 font-semibold text-primary">
                <Clock className="h-3.5 w-3.5" />
                Slot: {appointment.slot}
              </span>
              {patient.mobile ? (
                <span className="flex items-center gap-1">
                  <Phone className="h-3.5 w-3.5" /> {patient.mobile}
                </span>
              ) : null}
            </div>
          </div>
          <StatusBadge status={appointment.status} />
        </div>

        {appointment.reason ? (
          <p className="mt-3 text-xs text-foreground/90 leading-relaxed bg-surface/70 rounded-xl p-3 border border-border/40">
            <strong>Reason:</strong> {appointment.reason}
          </p>
        ) : null}

        <div className="mt-3 flex flex-wrap items-center gap-1.5">
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

      <div className="flex flex-wrap items-center justify-end gap-2 border-t border-border/50 pt-3">
        {onAccept && isBooked ? (
          <Button
            size="sm"
            onClick={onAccept}
            disabled={accepting}
            className="rounded-xl text-xs font-semibold shadow-soft tap-feedback"
          >
            <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" />
            {accepting ? "Accepting…" : "Accept Consultation"}
          </Button>
        ) : null}

        {onPrescribe ? (
          <Button
            size="sm"
            variant={isPrescribing ? "secondary" : "outline"}
            onClick={onPrescribe}
            className="rounded-xl text-xs font-semibold tap-feedback"
          >
            <FileEdit className="mr-1.5 h-3.5 w-3.5" />
            {isPrescribing ? "Close Prescription Form" : "Issue Prescription"}
          </Button>
        ) : null}
      </div>
    </div>
  );
}
