import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Loader2, Plus, Search, UserPlus, Users } from "lucide-react";
import { toast } from "sonner";
import { ROLE_LABEL, adminApi, asList, type Hospital, type Role, type User } from "@/lib/api";
import { RoleGate } from "@/components/RoleGate";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import { personName } from "@/lib/format";

export const Route = createFileRoute("/admin/dashboard")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Network administration — CityCare" },
      {
        name: "description",
        content: "Super admin control for CityCare hospitals, managers, doctors and user accounts.",
      },
      { property: "og:title", content: "Network administration — CityCare" },
      { property: "og:description", content: "Hospitals and users across the whole CityCare network." },
    ],
  }),
  component: () => (
    <RoleGate role="super_admin">
      <AdminDashboard />
    </RoleGate>
  ),
});

function hospitalStatus(hospital: Hospital): string {
  if (hospital.status) return hospital.status;
  return hospital.is_active === false ? "inactive" : "active";
}

function AdminDashboard() {
  const queryClient = useQueryClient();

  const hospitals = useQuery({
    queryKey: ["admin", "hospitals"],
    queryFn: async () => asList<Hospital>(await adminApi.hospitals()),
  });
  const users = useQuery({
    queryKey: ["admin", "users"],
    queryFn: async () => asList<User>(await adminApi.users()),
  });

  const hospitalList = hospitals.data ?? [];
  const userList = users.data ?? [];

  const invalidateHospitals = () => queryClient.invalidateQueries({ queryKey: ["admin", "hospitals"] });
  const invalidateUsers = () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] });

  const toggleStatus = useMutation({
    mutationFn: (hospital: Hospital) => {
      const active = hospitalStatus(hospital).toLowerCase() === "active";
      return adminApi.updateHospital(hospital.id, { status: active ? "inactive" : "active" });
    },
    onSuccess: () => {
      toast.success("Hospital status updated");
      invalidateHospitals();
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not update status"),
  });

  const deactivate = useMutation({
    mutationFn: (id: number | string) => adminApi.deactivateUser(id),
    onSuccess: () => {
      toast.success("User deactivated");
      invalidateUsers();
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not deactivate user"),
  });

  const [hospitalSearch, setHospitalSearch] = useState("");
  const [userSearch, setUserSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<"all" | Role>("all");

  const filteredHospitals = useMemo(() => {
    const term = hospitalSearch.trim().toLowerCase();
    if (!term) return hospitalList;
    return hospitalList.filter((h) =>
      [h.name, h.city, h.address].some((v) => (v ?? "").toString().toLowerCase().includes(term)),
    );
  }, [hospitalList, hospitalSearch]);

  const filteredUsers = useMemo(() => {
    const term = userSearch.trim().toLowerCase();
    return userList.filter((u) => {
      if (roleFilter !== "all" && u.role !== roleFilter) return false;
      if (!term) return true;
      return [u.first_name, u.last_name, u.email, u.mobile].some((v) =>
        (v ?? "").toString().toLowerCase().includes(term),
      );
    });
  }, [userList, userSearch, roleFilter]);

  return (
    <>
      <PageHeader
        eyebrow="Super admin"
        title="Network administration"
        description="Hospitals, managers, doctors and patient accounts across all of CityCare."
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Hospitals" value={hospitalList.length} icon={<Building2 className="h-4 w-4" />} />
        <StatCard label="Total users" value={userList.length} icon={<Users className="h-4 w-4" />} />
        <StatCard
          label="Doctors"
          value={userList.filter((u) => u.role === "doctor").length}
          icon={<UserPlus className="h-4 w-4" />}
        />
        <StatCard
          label="Patients"
          value={userList.filter((u) => u.role === "customer").length}
          icon={<Users className="h-4 w-4" />}
        />
      </div>

      <Tabs defaultValue="hospitals" className="mt-8">
        <TabsList className="mb-6 h-auto flex-wrap rounded-2xl bg-surface p-1.5">
          <TabsTrigger value="hospitals" className="rounded-xl px-4 py-2 text-sm">
            Hospitals
          </TabsTrigger>
          <TabsTrigger value="users" className="rounded-xl px-4 py-2 text-sm">
            Users
          </TabsTrigger>
        </TabsList>

        <TabsContent value="hospitals">
          <Panel
            title="Hospitals"
            description={`${filteredHospitals.length} of ${hospitalList.length} shown`}
            action={<HospitalDialog onDone={invalidateHospitals} />}
          >
            <div className="mb-5 max-w-sm">
              <SearchInput
                id="hospital-search"
                placeholder="Search by name, city or address"
                value={hospitalSearch}
                onChange={setHospitalSearch}
              />
            </div>

            {hospitals.isLoading ? (
              <LoadingRows />
            ) : hospitals.isError ? (
              <ErrorNote
                message={hospitals.error instanceof Error ? hospitals.error.message : "Could not load hospitals"}
              />
            ) : filteredHospitals.length === 0 ? (
              <EmptyState title="No hospitals found" description="Adjust your search or create a new hospital." />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[680px] text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                      <th className="pb-3 font-semibold">Hospital</th>
                      <th className="pb-3 font-semibold">City</th>
                      <th className="pb-3 font-semibold">Contact</th>
                      <th className="pb-3 font-semibold">Status</th>
                      <th className="pb-3 text-right font-semibold">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredHospitals.map((hospital) => (
                      <tr key={hospital.id} className="border-t border-border/70 transition-colors hover:bg-surface">
                        <td className="py-3.5 pr-4">
                          <p className="font-medium">{hospital.name}</p>
                          <p className="text-xs text-muted-foreground">{hospital.address ?? "—"}</p>
                        </td>
                        <td className="py-3.5 pr-4 text-muted-foreground">{hospital.city ?? "—"}</td>
                        <td className="py-3.5 pr-4 text-muted-foreground">
                          <p className="break-all">{hospital.contact_email ?? "—"}</p>
                          <p>{hospital.contact_phone ?? "—"}</p>
                        </td>
                        <td className="py-3.5 pr-4">
                          <StatusBadge status={hospitalStatus(hospital)} />
                        </td>
                        <td className="py-3.5">
                          <div className="flex justify-end gap-2">
                            <HospitalDialog hospital={hospital} onDone={invalidateHospitals} />
                            <Button
                              variant="ghost"
                              size="sm"
                              className="rounded-xl"
                              disabled={toggleStatus.isPending}
                              onClick={() => toggleStatus.mutate(hospital)}
                            >
                              {hospitalStatus(hospital).toLowerCase() === "active" ? "Deactivate" : "Activate"}
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </TabsContent>

        <TabsContent value="users">
          <Panel
            title="Users"
            description={`${filteredUsers.length} of ${userList.length} shown`}
            action={
              <div className="flex flex-wrap gap-2">
                <StaffDialog kind="manager" hospitals={hospitalList} onDone={invalidateUsers} />
                <StaffDialog kind="doctor" hospitals={hospitalList} onDone={invalidateUsers} />
              </div>
            }
          >
            <div className="mb-5 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
              <SearchInput
                id="user-search"
                placeholder="Search by name, email or mobile"
                value={userSearch}
                onChange={setUserSearch}
              />
              <Select value={roleFilter} onValueChange={(value) => setRoleFilter(value as "all" | Role)}>
                <SelectTrigger className="h-11 w-full rounded-xl sm:w-48">
                  <SelectValue placeholder="All roles" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All roles</SelectItem>
                  <SelectItem value="customer">Patients</SelectItem>
                  <SelectItem value="doctor">Doctors</SelectItem>
                  <SelectItem value="hospital_manager">Hospital managers</SelectItem>
                  <SelectItem value="super_admin">Super admins</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {users.isLoading ? (
              <LoadingRows />
            ) : users.isError ? (
              <ErrorNote message={users.error instanceof Error ? users.error.message : "Could not load users"} />
            ) : filteredUsers.length === 0 ? (
              <EmptyState title="No users found" description="Try a different search or role filter." />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                      <th className="pb-3 font-semibold">Name</th>
                      <th className="pb-3 font-semibold">Role</th>
                      <th className="pb-3 font-semibold">Contact</th>
                      <th className="pb-3 font-semibold">Hospital</th>
                      <th className="pb-3 font-semibold">Status</th>
                      <th className="pb-3 text-right font-semibold">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredUsers.map((user) => (
                      <tr key={user.id} className="border-t border-border/70 transition-colors hover:bg-surface">
                        <td className="py-3.5 pr-4 font-medium">{personName(user)}</td>
                        <td className="py-3.5 pr-4 text-muted-foreground">{ROLE_LABEL[user.role] ?? user.role}</td>
                        <td className="py-3.5 pr-4 text-muted-foreground">
                          <p className="break-all">{user.email}</p>
                          <p>{user.mobile}</p>
                        </td>
                        <td className="py-3.5 pr-4 text-muted-foreground">
                          {hospitalList.find((h) => String(h.id) === String(user.hospital_id))?.name ??
                            (user.hospital_id ? `#${user.hospital_id}` : "—")}
                        </td>
                        <td className="py-3.5 pr-4">
                          <StatusBadge status={user.is_active === false ? "inactive" : "active"} />
                        </td>
                        <td className="py-3.5">
                          <div className="flex justify-end">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="rounded-xl text-destructive hover:bg-destructive/10 hover:text-destructive"
                              disabled={user.is_active === false || deactivate.isPending}
                              onClick={() => deactivate.mutate(user.id)}
                            >
                              Deactivate
                            </Button>
                          </div>
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

function SearchInput({
  id,
  placeholder,
  value,
  onChange,
}: {
  id: string;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="relative">
      <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        id={id}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`${fieldInputClass} pl-10`}
      />
    </div>
  );
}

function HospitalDialog({ hospital, onDone }: { hospital?: Hospital; onDone: () => void }) {
  const editing = Boolean(hospital);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    name: hospital?.name ?? "",
    address: hospital?.address ?? "",
    city: hospital?.city ?? "",
    state: hospital?.state ?? "",
    contact_phone: hospital?.contact_phone ?? "",
    contact_email: hospital?.contact_email ?? "",
  });
  const [error, setError] = useState("");

  const mutation = useMutation({
    mutationFn: (body: Partial<Hospital>) =>
      editing && hospital ? adminApi.updateHospital(hospital.id, body) : adminApi.createHospital(body),
    onSuccess: () => {
      toast.success(editing ? "Hospital updated" : "Hospital created");
      setOpen(false);
      onDone();
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Something went wrong"),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {editing ? (
          <Button variant="ghost" size="sm" className="rounded-xl">
            Edit
          </Button>
        ) : (
          <Button size="sm" className="rounded-xl">
            <Plus className="mr-1.5 h-4 w-4" /> New hospital
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="rounded-2xl sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-display text-xl">
            {editing ? "Edit hospital" : "Create hospital"}
          </DialogTitle>
        </DialogHeader>
        <form
          className="grid gap-4 sm:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            setError("");
            if (form.name.trim().length < 2) {
              setError("Hospital name is required");
              return;
            }
            mutation.mutate(form);
          }}
        >
          <Field id="h-name" label="Name" className="sm:col-span-2">
            <Input
              id="h-name"
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
              className={fieldInputClass}
            />
          </Field>
          <Field id="h-city" label="City">
            <Input
              id="h-city"
              value={form.city}
              onChange={(e) => setForm((p) => ({ ...p, city: e.target.value }))}
              className={fieldInputClass}
            />
          </Field>
          <Field id="h-state" label="State">
            <Input
              id="h-state"
              value={form.state}
              onChange={(e) => setForm((p) => ({ ...p, state: e.target.value }))}
              className={fieldInputClass}
            />
          </Field>
          <Field id="h-phone" label="Phone">
            <Input
              id="h-phone"
              value={form.contact_phone}
              onChange={(e) => setForm((p) => ({ ...p, contact_phone: e.target.value }))}
              className={fieldInputClass}
            />
          </Field>
          <Field id="h-address" label="Address" className="sm:col-span-2">
            <Input
              id="h-address"
              value={form.address}
              onChange={(e) => setForm((p) => ({ ...p, address: e.target.value }))}
              className={fieldInputClass}
            />
          </Field>
          <Field id="h-email" label="Email" className="sm:col-span-2">
            <Input
              id="h-email"
              type="email"
              value={form.contact_email}
              onChange={(e) => setForm((p) => ({ ...p, contact_email: e.target.value }))}
              className={fieldInputClass}
            />
          </Field>
          {error ? (
            <div className="sm:col-span-2">
              <ErrorNote message={error} />
            </div>
          ) : null}
          <DialogFooter className="sm:col-span-2">
            <Button type="submit" className="rounded-xl" disabled={mutation.isPending}>
              {mutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              {editing ? "Save changes" : "Create hospital"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function StaffDialog({
  kind,
  hospitals,
  onDone,
}: {
  kind: "manager" | "doctor";
  hospitals: Hospital[];
  onDone: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    email: "",
    mobile: "",
    password: "",
    hospital_id: "",
  });
  const [error, setError] = useState("");

  const mutation = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      kind === "manager" ? adminApi.createManager(body) : adminApi.createDoctor(body),
    onSuccess: () => {
      toast.success(kind === "manager" ? "Manager created" : "Doctor created");
      setOpen(false);
      setForm({ first_name: "", last_name: "", email: "", mobile: "", password: "", hospital_id: "" });
      onDone();
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Something went wrong"),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant={kind === "manager" ? "outline" : "default"} className="rounded-xl">
          <UserPlus className="mr-1.5 h-4 w-4" /> New {kind}
        </Button>
      </DialogTrigger>
      <DialogContent className="rounded-2xl sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-display text-xl">
            Create {kind === "manager" ? "hospital manager" : "doctor"}
          </DialogTitle>
        </DialogHeader>
        <form
          className="grid gap-4 sm:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            setError("");
            if (!form.first_name.trim() || !form.last_name.trim()) {
              setError("First and last name are required");
              return;
            }
            if (!/^\S+@\S+\.\S+$/.test(form.email.trim())) {
              setError("Enter a valid email address");
              return;
            }
            if (form.password.length < 6) {
              setError("Password must be at least 6 characters");
              return;
            }
            if (!form.hospital_id) {
              setError("Select a hospital");
              return;
            }
            mutation.mutate({
              first_name: form.first_name.trim(),
              last_name: form.last_name.trim(),
              email: form.email.trim(),
              mobile: form.mobile.trim(),
              password: form.password,
              hospital_id: Number.isNaN(Number(form.hospital_id)) ? form.hospital_id : Number(form.hospital_id),
            });
          }}
        >
          <Field id={`${kind}-first`} label="First name">
            <Input
              id={`${kind}-first`}
              value={form.first_name}
              onChange={(e) => setForm((p) => ({ ...p, first_name: e.target.value }))}
              className={fieldInputClass}
            />
          </Field>
          <Field id={`${kind}-last`} label="Last name">
            <Input
              id={`${kind}-last`}
              value={form.last_name}
              onChange={(e) => setForm((p) => ({ ...p, last_name: e.target.value }))}
              className={fieldInputClass}
            />
          </Field>
          <Field id={`${kind}-email`} label="Email" className="sm:col-span-2">
            <Input
              id={`${kind}-email`}
              type="email"
              value={form.email}
              onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))}
              className={fieldInputClass}
            />
          </Field>
          <Field id={`${kind}-mobile`} label="Mobile">
            <Input
              id={`${kind}-mobile`}
              value={form.mobile}
              onChange={(e) => setForm((p) => ({ ...p, mobile: e.target.value }))}
              className={fieldInputClass}
            />
          </Field>
          <Field id={`${kind}-password`} label="Temporary password">
            <Input
              id={`${kind}-password`}
              type="password"
              value={form.password}
              onChange={(e) => setForm((p) => ({ ...p, password: e.target.value }))}
              className={fieldInputClass}
            />
          </Field>
          <div className="space-y-1.5 sm:col-span-2">
            <p className="text-sm font-medium">Hospital</p>
            <Select
              value={form.hospital_id}
              onValueChange={(value) => setForm((p) => ({ ...p, hospital_id: value }))}
            >
              <SelectTrigger className="h-11 rounded-xl">
                <SelectValue placeholder="Select a hospital" />
              </SelectTrigger>
              <SelectContent>
                {hospitals.map((hospital) => (
                  <SelectItem key={hospital.id} value={String(hospital.id)}>
                    {hospital.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {error ? (
            <div className="sm:col-span-2">
              <ErrorNote message={error} />
            </div>
          ) : null}
          <DialogFooter className="sm:col-span-2">
            <Button type="submit" className="rounded-xl" disabled={mutation.isPending}>
              {mutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Create {kind}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
