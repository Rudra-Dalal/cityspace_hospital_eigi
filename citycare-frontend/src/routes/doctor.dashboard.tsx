import { useMemo, useState } from "react";
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
  MapPin,
  Activity,
  Shield,
  Search,
  Sparkles,
  ArrowRight,
  Info,
} from "lucide-react";
import { toast } from "sonner";
import { appointmentsApi, asList, doctorApi, type Appointment } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
      { title: "Clinical Workspace — Medihub / CityCare" },
      {
        name: "description",
        content: "Your consulting schedule, patient queue, digital prescriptions, and clinical AI assistant.",
      },
      { property: "og:title", content: "Clinical Workspace — Medihub" },
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
  const [activeTab, setActiveTab] = useState<string>("today");
  const [searchQuery, setSearchQuery] = useState("");

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
      toast.success("Appointment successfully accepted");
      queryClient.invalidateQueries({ queryKey: ["doctor", "schedule"] });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Could not accept appointment"),
  });

  const today = useMemo(() => appointments.filter((a) => isToday(a.date)), [appointments]);
  const upcoming = useMemo(() => appointments.filter((a) => !isToday(a.date)), [appointments]);
  const statsData = stats.data;
  const profile = (info.data ?? {}) as Record<string, unknown>;

  const filteredAppointments = useMemo(() => {
    if (!searchQuery.trim()) return appointments;
    const q = searchQuery.toLowerCase();
    return appointments.filter((a) => {
      const patient = a.customer || {};
      const name = (a.patient_name || `${patient.first_name || ""} ${patient.last_name || ""}`).toLowerCase();
      const reason = (a.reason || "").toLowerCase();
      const symptoms = (a.symptoms || []).join(" ").toLowerCase();
      const slot = (a.slot || "").toLowerCase();
      return name.includes(q) || reason.includes(q) || symptoms.includes(q) || slot.includes(q);
    });
  }, [appointments, searchQuery]);

  const clinicName = String(profile["clinic_name"] || "CityCare Clinic");
  const clinicLocation = String(profile["clinic_location"] || "Dharampeth, Nagpur");
  const morningHours = String(profile["morning_hours"] || "10:00 to 13:00");
  const eveningHours = String(profile["evening_hours"] || "17:00 to 20:00");
  const slotDuration = String(profile["slot_duration_minutes"] || "30");

  const workingDays = [
    { day: "Mon", active: true },
    { day: "Tue", active: true },
    { day: "Wed", active: true },
    { day: "Thu", active: true },
    { day: "Fri", active: true },
    { day: "Sat", active: true },
    { day: "Sun", active: false },
  ];

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-16">
      <PageHeader
        eyebrow="Clinical Workspace"
        title={`Dr. ${personName(user, "Clinician")}`}
        description="Review patient consultations, issue digital prescriptions, manage clinical schedules, and query your AI assistant."
      />

      {/* Metric Stat Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Today's Clinic Queue"
          value={statsData ? ((statsData["today_visits"] as number) ?? today.length) : today.length}
          icon={<CalendarCheck className="h-4 w-4" />}
          hint="Scheduled for today"
        />
        <StatCard
          label="Upcoming Consultations"
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
          hint="All time records"
        />
        <StatCard
          label="Weekly Total"
          value={appointments.length}
          icon={<Clock className="h-4 w-4" />}
          hint="Active patient volume"
        />
      </div>

      {/* Main Clinical Workstation Grid */}
      <div className="grid gap-8 lg:grid-cols-[1.35fr_0.65fr] items-start">
        {/* Left Column: Consultation Tabs + Clinic Schedule + Clinical Reference */}
        <div className="space-y-8">
          {/* Consultation Management Tabs */}
          <Panel
            title="Consultation Workstation"
            description="Manage active appointments, accept incoming requests, and issue electronic prescriptions."
          >
            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
              <TabsList className="grid w-full grid-cols-3 rounded-xl bg-muted/60 p-1 mb-5">
                <TabsTrigger value="today" className="rounded-lg text-xs font-semibold flex items-center gap-1.5">
                  <CalendarCheck className="h-3.5 w-3.5" />
                  Today ({today.length})
                </TabsTrigger>
                <TabsTrigger value="upcoming" className="rounded-lg text-xs font-semibold flex items-center gap-1.5">
                  <CalendarDays className="h-3.5 w-3.5" />
                  Upcoming ({upcoming.length})
                </TabsTrigger>
                <TabsTrigger value="all" className="rounded-lg text-xs font-semibold flex items-center gap-1.5">
                  <Users className="h-3.5 w-3.5" />
                  All ({appointments.length})
                </TabsTrigger>
              </TabsList>

              {/* Today's Queue Tab */}
              <TabsContent value="today" className="space-y-4">
                <div className="flex items-center justify-between pb-2 border-b border-border/40">
                  <span className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5 text-primary" />
                    {formatDate(new Date().toISOString().slice(0, 10))}
                  </span>
                  <span className="text-xs font-semibold text-primary bg-primary/10 px-2.5 py-0.5 rounded-full border border-primary/20">
                    {today.length} {today.length === 1 ? "Patient" : "Patients"} Today
                  </span>
                </div>

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
                  <div className="rounded-2xl border border-dashed border-border/70 p-6 sm:p-8 text-center bg-card/40 space-y-4">
                    <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-primary/10 text-primary border border-primary/20 shadow-subtle">
                      <CalendarCheck className="h-6 w-6" />
                    </div>
                    <div>
                      <h3 className="font-display text-base font-bold text-foreground">
                        No Consultations Scheduled Today
                      </h3>
                      <p className="mt-1 text-xs text-muted-foreground max-w-sm mx-auto leading-relaxed">
                        Your clinic queue for today is currently clear. You can review upcoming bookings or query your Clinical AI Assistant.
                      </p>
                    </div>
                    {upcoming.length > 0 ? (
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => setActiveTab("upcoming")}
                        className="rounded-xl text-xs font-semibold tap-feedback"
                      >
                        View Upcoming Bookings ({upcoming.length})
                        <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                      </Button>
                    ) : null}
                  </div>
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
              </TabsContent>

              {/* Upcoming Consultations Tab */}
              <TabsContent value="upcoming" className="space-y-4">
                {schedule.isLoading ? (
                  <LoadingRows rows={2} />
                ) : upcoming.length === 0 ? (
                  <EmptyState
                    title="No Upcoming Consultations"
                    description="There are no patient appointments booked for future dates at this time."
                  />
                ) : (
                  <div className="space-y-3">
                    {upcoming.map((appointment) => (
                      <DoctorAppointmentItem
                        key={appointment.id}
                        appointment={appointment}
                        onAccept={() => accept.mutate(appointment.id)}
                        accepting={accept.isPending && accept.variables === appointment.id}
                      />
                    ))}
                  </div>
                )}
              </TabsContent>

              {/* All Consultations Tab */}
              <TabsContent value="all" className="space-y-4">
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    placeholder="Search consultations by patient, reason, symptom, or slot…"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10 h-10 rounded-xl text-xs bg-surface border-border/70"
                  />
                </div>

                {schedule.isLoading ? (
                  <LoadingRows rows={3} />
                ) : filteredAppointments.length === 0 ? (
                  <EmptyState
                    title="No Records Found"
                    description={
                      searchQuery
                        ? `No appointments matching "${searchQuery}". Try a different keyword.`
                        : "No patient consultation history available."
                    }
                  />
                ) : (
                  <div className="space-y-3">
                    {filteredAppointments.map((appointment) => (
                      <DoctorAppointmentItem
                        key={appointment.id}
                        appointment={appointment}
                        onAccept={() => accept.mutate(appointment.id)}
                        accepting={accept.isPending && accept.variables === appointment.id}
                      />
                    ))}
                  </div>
                )}
              </TabsContent>
            </Tabs>
          </Panel>

          {/* Clinical Facility & Practice Schedule */}
          <Panel
            title="Practice Schedule & Facility Affiliation"
            description="Active clinic hours, weekly consulting roster, and slot configurations."
          >
            <div className="grid gap-4 sm:grid-cols-2">
              {/* Facility Details */}
              <div className="rounded-2xl border border-border/70 bg-card/60 p-4 space-y-3">
                <div className="flex items-center gap-2.5">
                  <span className="grid h-8 w-8 place-items-center rounded-xl bg-primary/10 text-primary border border-primary/20">
                    <Building2 className="h-4 w-4" />
                  </span>
                  <div>
                    <h4 className="font-display text-sm font-bold text-foreground">
                      {clinicName}
                    </h4>
                    <p className="text-xs text-muted-foreground flex items-center gap-1">
                      <MapPin className="h-3 w-3 text-primary" />
                      {clinicLocation}
                    </p>
                  </div>
                </div>

                <div className="pt-2 border-t border-border/50 text-xs space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">Consultation Slot:</span>
                    <span className="font-semibold text-foreground">{slotDuration} mins / session</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">Booking Window:</span>
                    <span className="font-semibold text-foreground">7 Days in Advance</span>
                  </div>
                </div>
              </div>

              {/* Shift Hours */}
              <div className="rounded-2xl border border-border/70 bg-card/60 p-4 space-y-3">
                <div className="flex items-center gap-2.5">
                  <span className="grid h-8 w-8 place-items-center rounded-xl bg-primary/10 text-primary border border-primary/20">
                    <Clock className="h-4 w-4" />
                  </span>
                  <div>
                    <h4 className="font-display text-sm font-bold text-foreground">
                      Daily Consulting Shifts
                    </h4>
                    <p className="text-xs text-muted-foreground">Two daily practice windows</p>
                  </div>
                </div>

                <div className="pt-2 border-t border-border/50 text-xs space-y-2">
                  <div className="flex justify-between items-center bg-surface/50 p-2 rounded-xl border border-border/40">
                    <span className="text-muted-foreground flex items-center gap-1">
                      🌅 Morning Session
                    </span>
                    <span className="font-semibold text-foreground">{morningHours}</span>
                  </div>
                  <div className="flex justify-between items-center bg-surface/50 p-2 rounded-xl border border-border/40">
                    <span className="text-muted-foreground flex items-center gap-1">
                      🌇 Evening Session
                    </span>
                    <span className="font-semibold text-foreground">{eveningHours}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Weekly Days Roster */}
            <div className="mt-4 pt-4 border-t border-border/50">
              <p className="text-xs font-semibold text-foreground mb-2.5">
                Weekly Consulting Availability
              </p>
              <div className="flex flex-wrap items-center gap-2">
                {workingDays.map(({ day, active }) => (
                  <span
                    key={day}
                    className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-medium border ${
                      active
                        ? "bg-success/10 text-success border-success/30 font-semibold"
                        : "bg-muted/40 text-muted-foreground border-border/40 opacity-60"
                    }`}
                  >
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${
                        active ? "bg-success animate-pulse" : "bg-muted-foreground"
                      }`}
                    />
                    {day} {active ? "(Open)" : "(Off)"}
                  </span>
                ))}
              </div>
            </div>
          </Panel>

          {/* Clinical Guidelines & Triage Protocol Card */}
          <Panel
            title="Clinical Reference & Triage Protocols"
            description="Quick reference thresholds for vital signs, standard symptoms, and triage protocols."
          >
            <div className="grid gap-3 sm:grid-cols-3 text-xs">
              <div className="rounded-xl border border-border/60 bg-card/40 p-3.5 space-y-1.5">
                <div className="flex items-center gap-1.5 text-primary font-semibold">
                  <Thermometer className="h-3.5 w-3.5" />
                  <span>Normal Temp</span>
                </div>
                <p className="font-display text-sm font-bold text-foreground">98.6°F / 37.0°C</p>
                <p className="text-[11px] text-muted-foreground">Standard normative body baseline</p>
              </div>

              <div className="rounded-xl border border-border/60 bg-card/40 p-3.5 space-y-1.5">
                <div className="flex items-center gap-1.5 text-warning font-semibold">
                  <Activity className="h-3.5 w-3.5" />
                  <span>Low Grade Fever</span>
                </div>
                <p className="font-display text-sm font-bold text-foreground">99.0°F – 100.4°F</p>
                <p className="text-[11px] text-muted-foreground">Hydration & antipyretic evaluation</p>
              </div>

              <div className="rounded-xl border border-border/60 bg-card/40 p-3.5 space-y-1.5">
                <div className="flex items-center gap-1.5 text-destructive font-semibold">
                  <Shield className="h-3.5 w-3.5" />
                  <span>High Fever Alert</span>
                </div>
                <p className="font-display text-sm font-bold text-foreground">&gt; 102.0°F / 38.9°C</p>
                <p className="text-[11px] text-muted-foreground">Immediate clinical intervention</p>
              </div>
            </div>

            <div className="mt-3.5 rounded-xl bg-surface/70 border border-border/50 p-3 text-xs flex items-start gap-2.5">
              <Info className="h-4 w-4 text-primary shrink-0 mt-0.5" />
              <p className="text-muted-foreground leading-relaxed text-[11px]">
                <strong className="text-foreground font-semibold">E-Prescription Verification:</strong> When issuing prescriptions, ensure medicine frequency, dosage, and dietary instructions are provided. Digitally generated PDFs are permanently indexed and downloadable by verified patients.
              </p>
            </div>
          </Panel>
        </div>

        {/* Right Sidebar: Profile Credentials & AI Clinical Assistant */}
        <div className="space-y-6">
          {/* Physician Profile Card */}
          <Panel title="Physician Credentials">
            <div className="space-y-3 text-xs">
              <div className="flex items-center gap-3 border-b border-border/50 pb-3">
                <span className="grid h-11 w-11 place-items-center rounded-2xl bg-primary/10 text-sm font-bold text-primary border border-primary/20 shadow-subtle">
                  {user?.first_name?.[0]}
                  {user?.last_name?.[0]}
                </span>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-display font-bold text-sm text-foreground truncate">
                      Dr. {user?.first_name} {user?.last_name}
                    </p>
                  </div>
                  <p className="text-primary font-semibold truncate">
                    {String(
                      profile["specialization"] || user?.specialization || "General Physician",
                    )}
                  </p>
                </div>
              </div>

              <div className="space-y-2 pt-1">
                {profile["qualification"] || user?.qualification ? (
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">Qualification:</span>
                    <span className="font-semibold text-foreground">
                      {String(profile["qualification"] || user?.qualification)}
                    </span>
                  </div>
                ) : null}

                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Affiliated Center:</span>
                  <span className="font-semibold text-foreground truncate max-w-[160px] text-right">
                    {clinicName}
                  </span>
                </div>

                <div className="flex justify-between items-center">
                  <span className="text-muted-foreground">Duty Status:</span>
                  <span className="inline-flex items-center gap-1.5 text-success font-semibold">
                    <span className="h-2 w-2 rounded-full bg-success animate-ping" />
                    Active On Duty
                  </span>
                </div>

                {user?.email ? (
                  <div className="flex items-center gap-2 text-muted-foreground pt-2 border-t border-border/50">
                    <Mail className="h-3.5 w-3.5 text-primary shrink-0" />
                    <span className="truncate">{user.email}</span>
                  </div>
                ) : null}
              </div>
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
              <span className="grid h-7 w-7 place-items-center rounded-xl bg-secondary text-foreground text-xs font-bold border border-border/50">
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
            <strong className="text-foreground font-semibold">Reason:</strong> {appointment.reason}
          </p>
        ) : null}

        <div className="mt-3 flex flex-wrap items-center gap-1.5">
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
