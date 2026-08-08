import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Loader2, Stethoscope, CalendarRange } from "lucide-react";
import { toast } from "sonner";
import { asList, managerApi, type Appointment, type Hospital, type User } from "@/lib/api";
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
      { property: "og:description", content: "Hospital profile, doctors and appointments in one place." },
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

  const hospital = useQuery({ queryKey: ["manager", "hospital"], queryFn: () => managerApi.hospital() });
  const doctors = useQuery({
    queryKey: ["manager", "doctors"],
    queryFn: async () => asList<User>(await managerApi.doctors()),
  });
  const appointments = useQuery({
    queryKey: ["manager", "appointments"],
    queryFn: async () => asList<Appointment>(await managerApi.appointments()),
  });

  const [form, setForm] = useState<{ name: string; address: string; city: string; contact_phone: string; contact_email: string }>({
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
      toast.success("Hospital profile updated");
      queryClient.invalidateQueries({ queryKey: ["manager", "hospital"] });
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not save"),
  });

  const list = appointments.data ?? [];
  const todayCount = list.filter((a) => isToday(a.date)).length;

  return (
    <>
      <PageHeader
        eyebrow="Hospital manager"
        title={hospital.data?.name ?? "Your hospital"}
        description="Keep your listing accurate, see your care team and follow the appointment book."
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Doctors" value={doctors.data?.length ?? "—"} icon={<Stethoscope className="h-4 w-4" />} />
        <StatCard label="Appointments today" value={todayCount} icon={<CalendarRange className="h-4 w-4" />} />
        <StatCard label="Total appointments" value={list.length} icon={<Building2 className="h-4 w-4" />} />
      </div>

      <Tabs defaultValue="profile" className="mt-8">
        <TabsList className="mb-6 h-auto flex-wrap rounded-2xl bg-surface p-1.5">
          <TabsTrigger value="profile" className="rounded-xl px-4 py-2 text-sm">
            Hospital profile
          </TabsTrigger>
          <TabsTrigger value="doctors" className="rounded-xl px-4 py-2 text-sm">
            Doctors
          </TabsTrigger>
          <TabsTrigger value="appointments" className="rounded-xl px-4 py-2 text-sm">
            Appointments
          </TabsTrigger>
        </TabsList>

        <TabsContent value="profile">
          <Panel title="Profile details" description="Patients see this information when booking.">
            {hospital.isLoading ? (
              <LoadingRows rows={3} />
            ) : hospital.isError ? (
              <ErrorNote
                message={hospital.error instanceof Error ? hospital.error.message : "Could not load hospital"}
              />
            ) : (
              <form
                className="grid gap-4 sm:grid-cols-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  save.mutate(form);
                }}
              >
                <Field id="name" label="Hospital name">
                  <Input
                    id="name"
                    value={form.name}
                    onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                    className={fieldInputClass}
                  />
                </Field>
                <Field id="city" label="City">
                  <Input
                    id="city"
                    value={form.city}
                    onChange={(e) => setForm((p) => ({ ...p, city: e.target.value }))}
                    className={fieldInputClass}
                  />
                </Field>
                <Field id="address" label="Address" className="sm:col-span-2">
                  <Input
                    id="address"
                    value={form.address}
                    onChange={(e) => setForm((p) => ({ ...p, address: e.target.value }))}
                    className={fieldInputClass}
                  />
                </Field>
                <Field id="phone" label="Phone">
                  <Input
                    id="phone"
                    value={form.contact_phone}
                    onChange={(e) => setForm((p) => ({ ...p, contact_phone: e.target.value }))}
                    className={fieldInputClass}
                  />
                </Field>
                <Field id="email" label="Email">
                  <Input
                    id="email"
                    type="email"
                    value={form.contact_email}
                    onChange={(e) => setForm((p) => ({ ...p, contact_email: e.target.value }))}
                    className={fieldInputClass}
                  />
                </Field>
                <div className="sm:col-span-2">
                  <Button type="submit" className="rounded-xl" disabled={save.isPending}>
                    {save.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    Save changes
                  </Button>
                </div>
              </form>
            )}
          </Panel>
        </TabsContent>

        <TabsContent value="doctors">
          <Panel title="Care team" description="Doctors assigned to your hospital">
            {doctors.isLoading ? (
              <LoadingRows />
            ) : doctors.isError ? (
              <ErrorNote message={doctors.error instanceof Error ? doctors.error.message : "Could not load doctors"} />
            ) : (doctors.data ?? []).length === 0 ? (
              <EmptyState
                title="No doctors yet"
                description="Ask a super admin to assign doctors to this hospital."
              />
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {(doctors.data ?? []).map((doctor) => (
                  <div key={doctor.id} className="hover-lift fade-rise rounded-2xl bg-surface p-5">
                    <p className="font-display text-lg leading-tight">Dr. {personName(doctor)}</p>
                    <p className="mt-1.5 break-all text-sm text-muted-foreground">{doctor.email}</p>
                    <p className="mt-1 text-sm text-muted-foreground">{doctor.mobile}</p>
                    <div className="mt-3">
                      <StatusBadge status={doctor.is_active === false ? "inactive" : "active"} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </TabsContent>

        <TabsContent value="appointments">
          <Panel title="Appointment book" description="Every appointment booked at your hospital">
            {appointments.isLoading ? (
              <LoadingRows />
            ) : appointments.isError ? (
              <ErrorNote
                message={
                  appointments.error instanceof Error ? appointments.error.message : "Could not load appointments"
                }
              />
            ) : list.length === 0 ? (
              <EmptyState title="No appointments yet" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                      <th className="pb-3 font-semibold">Date</th>
                      <th className="pb-3 font-semibold">Slot</th>
                      <th className="pb-3 font-semibold">Patient</th>
                      <th className="pb-3 font-semibold">Doctor</th>
                      <th className="pb-3 font-semibold">Reason</th>
                      <th className="pb-3 font-semibold">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {list.map((appointment) => (
                      <tr key={appointment.id} className="border-t border-border/70 transition-colors hover:bg-surface">
                        <td className="py-3.5 pr-4 font-medium">{formatDate(appointment.date)}</td>
                        <td className="py-3.5 pr-4 text-muted-foreground">{appointment.slot}</td>
                        <td className="py-3.5 pr-4">{appointment.patient_name ?? personName(appointment.customer)}</td>
                        <td className="py-3.5 pr-4">{appointment.doctor_name ?? personName(appointment.doctor)}</td>
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
        </TabsContent>
      </Tabs>
    </>
  );
}
