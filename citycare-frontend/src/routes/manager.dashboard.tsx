import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  Loader2,
  Stethoscope,
  CalendarRange,
  Users,
  Mail,
  Phone,
  MapPin,
  CalendarCheck,
  Save,
  Clock,
  User,
} from "lucide-react";
import { toast } from "sonner";
import {
  asList,
  managerApi,
  type Appointment,
  type Hospital,
  type User as UserType,
} from "@/lib/api";
import { RoleGate } from "@/components/RoleGate";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Field, fieldInputClass } from "@/components/Field";
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

export const Route = createFileRoute("/manager/dashboard")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Hospital management — CityCare" },
      {
        name: "description",
        content: "Manage your hospital profile, care team and appointment book inside CityCare.",
      },
      { property: "og:title", content: "Hospital management — CityCare" },
      {
        property: "og:description",
        content: "Hospital profile, doctors and appointments in one place.",
      },
    ],
  }),
  component: () => (
    <RoleGate role="hospital_manager">
      <ManagerDashboard />
    </RoleGate>
  ),
});

function ManagerDashboard() {
  const queryClient = useQueryClient();

  const hospital = useQuery({
    queryKey: ["manager", "hospital"],
    queryFn: () => managerApi.hospital(),
  });
  const doctors = useQuery({
    queryKey: ["manager", "doctors"],
    queryFn: async () => asList<UserType>(await managerApi.doctors()),
  });
  const appointments = useQuery({
    queryKey: ["manager", "appointments"],
    queryFn: async () => asList<Appointment>(await managerApi.appointments()),
  });

  const [form, setForm] = useState<{
    name: string;
    address: string;
    city: string;
    contact_phone: string;
    contact_email: string;
  }>({
    name: "",
    address: "",
    city: "",
    contact_phone: "",
    contact_email: "",
  });

  useEffect(() => {
    const data = hospital.data;
    if (!data) return;
    setForm({
      name: data.name ?? "",
      address: data.address ?? "",
      city: data.city ?? "",
      contact_phone: data.contact_phone ?? "",
      contact_email: data.contact_email ?? "",
    });
  }, [hospital.data]);

  const save = useMutation({
    mutationFn: (body: Partial<Hospital>) => managerApi.updateHospital(body),
    onSuccess: () => {
      toast.success("Hospital profile updated successfully");
      queryClient.invalidateQueries({ queryKey: ["manager", "hospital"] });
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : "Could not save changes"),
  });

  const list = appointments.data ?? [];
  const todayCount = list.filter((a) => isToday(a.date)).length;

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12">
      <PageHeader
        eyebrow="Hospital Operations"
        title={hospital.data?.name ?? "Branch Dashboard"}
        description="Maintain branch information, oversee affiliated physicians, and track live patient booking volume."
      />

      {/* Stat Cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label="Care Team Doctors"
          value={doctors.data?.length ?? "—"}
          icon={<Stethoscope className="h-4 w-4" />}
          hint="Assigned to this branch"
        />
        <StatCard
          label="Appointments Today"
          value={todayCount}
          icon={<CalendarRange className="h-4 w-4" />}
          hint="Scheduled consultations"
        />
        <StatCard
          label="Total Bookings"
          value={list.length}
          icon={<Building2 className="h-4 w-4" />}
          hint="All-time appointment volume"
        />
      </div>

      <Tabs defaultValue="profile" className="mt-8 space-y-6">
        <TabsList className="h-auto flex-wrap rounded-2xl bg-secondary/60 p-1.5 border border-border/60">
          <TabsTrigger
            value="profile"
            className="rounded-xl px-5 py-2 text-xs font-bold tap-feedback"
          >
            Branch Profile
          </TabsTrigger>
          <TabsTrigger
            value="doctors"
            className="rounded-xl px-5 py-2 text-xs font-bold tap-feedback"
          >
            Care Team ({doctors.data?.length ?? 0})
          </TabsTrigger>
          <TabsTrigger
            value="appointments"
            className="rounded-xl px-5 py-2 text-xs font-bold tap-feedback"
          >
            Appointment Register ({list.length})
          </TabsTrigger>
        </TabsList>

        {/* Profile Settings Tab */}
        <TabsContent value="profile" className="fade-rise">
          <Panel
            title="Branch Profile & Contact"
            description="Information displayed to patients during appointment booking."
          >
            {hospital.isLoading ? (
              <LoadingRows rows={3} />
            ) : hospital.isError ? (
              <ErrorNote
                message={
                  hospital.error instanceof Error
                    ? hospital.error.message
                    : "Could not load hospital details"
                }
                onRetry={() => hospital.refetch()}
              />
            ) : (
              <form
                className="grid gap-4 sm:grid-cols-2 max-w-4xl"
                onSubmit={(event) => {
                  event.preventDefault();
                  save.mutate(form);
                }}
              >
                <Field id="name" label="Hospital Branch Name">
                  <Input
                    id="name"
                    value={form.name}
                    onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                    className={fieldInputClass}
                    required
                  />
                </Field>
                <Field id="city" label="City / Region">
                  <Input
                    id="city"
                    value={form.city}
                    onChange={(e) => setForm((p) => ({ ...p, city: e.target.value }))}
                    className={fieldInputClass}
                    required
                  />
                </Field>
                <Field id="address" label="Street Address" className="sm:col-span-2">
                  <Input
                    id="address"
                    value={form.address}
                    onChange={(e) => setForm((p) => ({ ...p, address: e.target.value }))}
                    className={fieldInputClass}
                  />
                </Field>
                <Field id="phone" label="Contact Telephone">
                  <Input
                    id="phone"
                    value={form.contact_phone}
                    onChange={(e) => setForm((p) => ({ ...p, contact_phone: e.target.value }))}
                    className={fieldInputClass}
                  />
                </Field>
                <Field id="email" label="Contact Email">
                  <Input
                    id="email"
                    type="email"
                    value={form.contact_email}
                    onChange={(e) => setForm((p) => ({ ...p, contact_email: e.target.value }))}
                    className={fieldInputClass}
                  />
                </Field>
                <div className="sm:col-span-2 pt-2">
                  <Button
                    type="submit"
                    className="rounded-xl font-bold shadow-soft tap-feedback px-6 h-11"
                    disabled={save.isPending}
                  >
                    {save.isPending ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Save className="mr-2 h-4 w-4" />
                    )}
                    Save Branch Changes
                  </Button>
                </div>
              </form>
            )}
          </Panel>
        </TabsContent>

        {/* Doctors Care Team Tab */}
        <TabsContent value="doctors" className="fade-rise">
          <Panel
            title="Hospital Medical Care Team"
            description="Physicians actively practicing at this facility."
          >
            {doctors.isLoading ? (
              <LoadingRows rows={3} />
            ) : doctors.isError ? (
              <ErrorNote
                message={
                  doctors.error instanceof Error ? doctors.error.message : "Could not load doctors"
                }
                onRetry={() => doctors.refetch()}
              />
            ) : (doctors.data ?? []).length === 0 ? (
              <EmptyState
                title="No physicians assigned"
                description="Contact the Super Administrator to associate doctors with this hospital branch."
                icon={<Stethoscope className="h-6 w-6 opacity-60" />}
              />
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {(doctors.data ?? []).map((doctor) => (
                  <div
                    key={doctor.id}
                    className="hover-lift fade-rise rounded-2xl border border-border/70 bg-card p-5 shadow-subtle flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="font-display text-base font-bold text-foreground">
                            Dr. {personName(doctor)}
                          </p>
                          <p className="text-xs font-semibold text-primary mt-0.5">
                            {doctor.specialization || "General Medicine"}
                          </p>
                        </div>
                        <StatusBadge status={doctor.is_active === false ? "inactive" : "active"} />
                      </div>

                      <p className="mt-3 text-xs text-muted-foreground break-all">{doctor.email}</p>
                      {doctor.mobile ? (
                        <p className="mt-1 text-xs text-muted-foreground">{doctor.mobile}</p>
                      ) : null}
                    </div>

                    <div className="mt-4 border-t border-border/50 pt-2.5 text-[11px] text-muted-foreground flex items-center justify-between">
                      <span>{doctor.working_hours || "10:00 - 20:00"}</span>
                      <span className="truncate max-w-[120px]">
                        {doctor.available_days?.join(", ") || "Mon - Sat"}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </TabsContent>

        {/* Appointments Register Tab */}
        <TabsContent value="appointments" className="fade-rise">
          <Panel
            title="Branch Appointment Register"
            description="Consolidated record of all visits across this hospital."
          >
            {appointments.isLoading ? (
              <LoadingRows rows={4} />
            ) : appointments.isError ? (
              <ErrorNote
                message={
                  appointments.error instanceof Error
                    ? appointments.error.message
                    : "Could not load appointments"
                }
                onRetry={() => appointments.refetch()}
              />
            ) : list.length === 0 ? (
              <EmptyState
                title="No appointments recorded"
                description="Patient bookings will populate in real time."
              />
            ) : (
              <div className="overflow-x-auto rounded-2xl border border-border/60">
                <table className="w-full min-w-[700px] text-sm text-left">
                  <thead className="bg-surface border-b border-border/60 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                    <tr>
                      <th className="py-3.5 px-4">Date</th>
                      <th className="py-3.5 px-4">Time Slot</th>
                      <th className="py-3.5 px-4">Patient</th>
                      <th className="py-3.5 px-4">Physician</th>
                      <th className="py-3.5 px-4">Reason / Symptoms</th>
                      <th className="py-3.5 px-4">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/50 bg-card">
                    {list.map((appointment) => (
                      <tr key={appointment.id} className="transition-colors hover:bg-surface/50">
                        <td className="py-3.5 px-4 font-semibold text-foreground whitespace-nowrap">
                          {formatDate(appointment.date)}
                        </td>
                        <td className="py-3.5 px-4 text-xs font-semibold text-primary whitespace-nowrap">
                          {appointment.slot}
                        </td>
                        <td className="py-3.5 px-4 text-xs font-medium text-foreground">
                          {appointment.patient_name ?? personName(appointment.customer)}
                        </td>
                        <td className="py-3.5 px-4 text-xs font-medium text-foreground">
                          {appointment.doctor_name
                            ? `Dr. ${appointment.doctor_name}`
                            : personName(appointment.doctor)}
                        </td>
                        <td className="py-3.5 px-4 text-xs text-muted-foreground max-w-[200px] truncate">
                          {appointment.reason ?? "—"}
                        </td>
                        <td className="py-3.5 px-4 whitespace-nowrap">
                          <StatusBadge status={appointment.status ?? "booked"} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </TabsContent>
      </Tabs>
    </div>
  );
}
