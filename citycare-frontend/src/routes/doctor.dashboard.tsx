import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { CalendarCheck, CalendarDays, Clock, Mail, Phone, Users } from "lucide-react";
import { asList, doctorApi, type Appointment } from "@/lib/api";
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

export const Route = createFileRoute("/doctor/dashboard")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Doctor schedule — CityCare" },
      { name: "description", content: "Your CityCare consulting schedule, appointment volume and profile details." },
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

  const info = useQuery({ queryKey: ["doctor", "info"], queryFn: () => doctorApi.info() });
  const stats = useQuery({ queryKey: ["doctor", "stats"], queryFn: () => doctorApi.stats() });
  const schedule = useQuery({
    queryKey: ["doctor", "schedule"],
    queryFn: async () => asList<Appointment>(await doctorApi.schedule()),
  });

  const appointments = schedule.data ?? [];
  const today = appointments.filter((a) => isToday(a.date));
  const upcoming = appointments.filter((a) => !isToday(a.date));
  const statsData = stats.data;
  const profile = (info.data ?? {}) as Record<string, unknown>;

  return (
    <>
      <PageHeader
        eyebrow="Doctor"
        title={`Dr. ${personName(user, "Clinician")}`}
        description="Your consulting schedule and patient volume across the CityCare network."
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Appointments today"
          value={statsData ? (statsData["today_visits"] as number ?? today.length) : today.length}
          icon={<CalendarCheck className="h-4 w-4" />}
        />
        <StatCard
          label="Upcoming"
          value={statsData ? (statsData["upcoming_visits"] as number ?? upcoming.length) : upcoming.length}
          icon={<CalendarDays className="h-4 w-4" />}
        />
        <StatCard
          label="Total patients"
          value={statsData ? (statsData["total_patients"] as number ?? "—") : "—"}
          icon={<Users className="h-4 w-4" />}
        />
        <StatCard
          label="Schedule items"
          value={appointments.length}
          icon={<Clock className="h-4 w-4" />}
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_0.6fr]">
        <div className="space-y-6">
          <Panel title="Today" description={formatDate(new Date().toISOString().slice(0, 10))}>
            {schedule.isLoading ? (
              <LoadingRows />
            ) : schedule.isError ? (
              <ErrorNote
                message={schedule.error instanceof Error ? schedule.error.message : "Could not load schedule"}
              />
            ) : today.length === 0 ? (
              <EmptyState title="Nothing on today" description="Enjoy the quiet clinic." />
            ) : (
              <Timeline items={today} />
            )}
          </Panel>

          <Panel title="Coming up" description="The rest of your booked schedule">
            {schedule.isLoading ? (
              <LoadingRows rows={2} />
            ) : upcoming.length === 0 ? (
              <EmptyState title="No further appointments booked" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[520px] text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                      <th className="pb-3 font-semibold">Date</th>
                      <th className="pb-3 font-semibold">Slot</th>
                      <th className="pb-3 font-semibold">Patient</th>
                      <th className="pb-3 font-semibold">Reason</th>
                      <th className="pb-3 font-semibold">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {upcoming.map((appointment) => (
                      <tr key={appointment.id} className="border-t border-border/70 transition-colors hover:bg-surface">
                        <td className="py-3.5 pr-4 font-medium">{formatDate(appointment.date)}</td>
                        <td className="py-3.5 pr-4 text-muted-foreground">{appointment.slot}</td>
                        <td className="py-3.5 pr-4">
                          {appointment.patient_name ?? personName(appointment.customer)}
                        </td>
                        <td className="max-w-[220px] truncate py-3.5 pr-4 text-muted-foreground">
                          {appointment.reason ?? "—"}
                        </td>
                        <td className="py-3.5">
                          <StatusBadge status={appointment.status ?? "booked"} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>

        <Panel title="Profile">
          {info.isLoading ? (
            <LoadingRows rows={2} />
          ) : (
            <dl className="space-y-4 text-sm">
              <div>
                <dt className="text-xs uppercase tracking-wider text-muted-foreground">Name</dt>
                <dd className="mt-1 font-medium">{personName(user)}</dd>
              </div>
              <div>
                <dt className="flex items-center gap-1.5 text-xs uppercase tracking-wider text-muted-foreground">
                  <Mail className="h-3 w-3" /> Email
                </dt>
                <dd className="mt-1 break-all font-medium">{user?.email ?? "—"}</dd>
              </div>
              <div>
                <dt className="flex items-center gap-1.5 text-xs uppercase tracking-wider text-muted-foreground">
                  <Phone className="h-3 w-3" /> Mobile
                </dt>
                <dd className="mt-1 font-medium">{user?.mobile ?? "—"}</dd>
              </div>
              {Object.entries(profile)
                .filter(
                  ([key, value]) =>
                    !["id", "first_name", "last_name", "email", "mobile", "role", "password"].includes(key) &&
                    (typeof value === "string" || typeof value === "number"),
                )
                .map(([key, value]) => (
                  <div key={key}>
                    <dt className="text-xs uppercase tracking-wider text-muted-foreground">
                      {key.replace(/_/g, " ")}
                    </dt>
                    <dd className="mt-1 font-medium">{String(value)}</dd>
                  </div>
                ))}
            </dl>
          )}
        </Panel>
      </div>
    </>
  );
}

function Timeline({ items }: { items: Appointment[] }) {
  return (
    <ol className="relative space-y-4 border-l border-border pl-6">
      {items.map((appointment) => (
        <li key={appointment.id} className="fade-rise relative">
          <span className="absolute -left-[31px] top-3 h-2.5 w-2.5 rounded-full bg-primary ring-4 ring-primary-soft" />
          <div className="hover-lift rounded-2xl bg-surface p-4">
            <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3">
              <div className="min-w-0">
                <p className="font-display text-base leading-tight">{appointment.slot}</p>
                <p className="mt-1 truncate text-sm text-muted-foreground">
                  {appointment.patient_name ?? personName(appointment.customer, "Patient")}
                </p>
              </div>
              <StatusBadge status={appointment.status ?? "booked"} />
            </div>
            {appointment.reason ? (
              <p className="mt-3 text-sm text-foreground/90">{appointment.reason}</p>
            ) : null}
            {appointment.symptoms?.length ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {appointment.symptoms.map((symptom) => (
                  <span
                    key={symptom}
                    className="rounded-full bg-card px-2.5 py-1 text-xs font-medium capitalize text-muted-foreground"
                  >
                    {symptom}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        </li>
      ))}
    </ol>
  );
}
