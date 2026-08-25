import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  Loader2,
  Plus,
  Search,
  UserPlus,
  Users,
  ShieldCheck,
  Stethoscope,
  Power,
  Edit2,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import {
  ROLE_LABEL,
  adminApi,
  asList,
  type Hospital,
  type Role,
  type User as UserType,
} from "@/lib/api";
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
      { title: "Network Administration — Medihub / CityCare" },
      {
        name: "description",
        content: "Hospital management, medical staffing, and user governance across the clinical network.",
      },
      { property: "og:title", content: "Network Administration — Medihub" },
      {
        property: "og:description",
        content: "Hospitals and users across the whole CityCare network.",
      },
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
    queryFn: async () => asList<UserType>(await adminApi.users()),
  });

  const hospitalList = useMemo(() => hospitals.data ?? [], [hospitals.data]);
  const userList = useMemo(() => users.data ?? [], [users.data]);

  const invalidateHospitals = () =>
    queryClient.invalidateQueries({ queryKey: ["admin", "hospitals"] });
  const invalidateUsers = () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] });

  const toggleStatus = useMutation({
    mutationFn: (hospital: Hospital) => {
      const active = hospitalStatus(hospital).toLowerCase() === "active";
      return adminApi.updateHospital(hospital.id, { status: active ? "inactive" : "active" });
    },
    onSuccess: () => {
      toast.success("Hospital status updated successfully");
      invalidateHospitals();
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : "Could not update status"),
  });

  const deactivate = useMutation({
    mutationFn: (id: number | string) => adminApi.deactivateUser(id),
    onSuccess: () => {
      toast.success("User account deactivated");
      invalidateUsers();
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : "Could not deactivate user"),
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
    <div className="space-y-8 max-w-7xl mx-auto pb-16">
      <PageHeader
        eyebrow="Network Oversight"
        title="Network Administration"
        description="Comprehensive governance over hospital branches, medical staff rosters, and clinical user accounts across the Medihub network."
      />

      {/* Network Metrics */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Hospital Facilities"
          value={hospitalList.length}
          icon={<Building2 className="h-4 w-4" />}
          hint="Registered branches"
        />
        <StatCard
          label="Total User Accounts"
          value={userList.length}
          icon={<Users className="h-4 w-4" />}
          hint="Across all permissions"
        />
        <StatCard
          label="Practicing Physicians"
          value={userList.filter((u) => u.role === "doctor").length}
          icon={<Stethoscope className="h-4 w-4" />}
          hint="Active clinical staff"
        />
        <StatCard
          label="Verified Patients"
          value={userList.filter((u) => u.role === "customer").length}
          icon={<ShieldCheck className="h-4 w-4" />}
          hint="Registered patient accounts"
        />
      </div>

      <Tabs defaultValue="hospitals" className="mt-8 space-y-6">
        <TabsList className="h-auto flex-wrap rounded-2xl bg-secondary/60 p-1.5 border border-border/60">
          <TabsTrigger
            value="hospitals"
            className="rounded-xl px-5 py-2 text-xs font-semibold tap-feedback"
          >
            Hospital Branches ({hospitalList.length})
          </TabsTrigger>
          <TabsTrigger
            value="users"
            className="rounded-xl px-5 py-2 text-xs font-semibold tap-feedback"
          >
            User Directory ({userList.length})
          </TabsTrigger>
        </TabsList>

        {/* Hospitals Management Tab */}
        <TabsContent value="hospitals" className="fade-rise">
          <Panel
            title="Hospital Branches"
            description={`${filteredHospitals.length} of ${hospitalList.length} branch${hospitalList.length === 1 ? "" : "es"} displayed`}
            action={<HospitalDialog onDone={invalidateHospitals} />}
          >
            <div className="mb-5 max-w-sm">
              <SearchInput
                id="hospital-search"
                placeholder="Filter by branch name, city, address…"
                value={hospitalSearch}
                onChange={setHospitalSearch}
              />
            </div>

            {hospitals.isLoading ? (
              <LoadingRows rows={4} />
            ) : hospitals.isError ? (
              <ErrorNote
                message={
                  hospitals.error instanceof Error
                    ? hospitals.error.message
                    : "Could not load hospitals"
                }
                onRetry={() => hospitals.refetch()}
              />
            ) : filteredHospitals.length === 0 ? (
              <EmptyState
                title="No hospitals found"
                description="Adjust your search criteria or register a new branch."
              />
            ) : (
              <div className="overflow-x-auto rounded-2xl border border-border/60">
                <table className="w-full min-w-[700px] text-sm text-left">
                  <thead className="bg-surface border-b border-border/60 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                    <tr>
                      <th className="py-3.5 px-4">Hospital Branch</th>
                      <th className="py-3.5 px-4">City</th>
                      <th className="py-3.5 px-4">Contact</th>
                      <th className="py-3.5 px-4">Status</th>
                      <th className="py-3.5 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/50 bg-card">
                    {filteredHospitals.map((hospital) => {
                      const isActive = hospitalStatus(hospital).toLowerCase() === "active";
                      return (
                        <tr key={hospital.id} className="transition-colors hover:bg-surface/50">
                          <td className="py-3.5 px-4">
                            <p className="font-bold text-foreground">{hospital.name}</p>
                            <p className="text-xs text-muted-foreground">
                              {hospital.address ?? "—"}
                            </p>
                          </td>
                          <td className="py-3.5 px-4 text-xs font-medium text-foreground">
                            {hospital.city ?? "—"}
                          </td>
                          <td className="py-3.5 px-4 text-xs text-muted-foreground">
                            <p className="break-all">{hospital.contact_email ?? "—"}</p>
                            <p>{hospital.contact_phone ?? "—"}</p>
                          </td>
                          <td className="py-3.5 px-4 whitespace-nowrap">
                            <StatusBadge status={hospitalStatus(hospital)} />
                          </td>
                          <td className="py-3.5 px-4 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <HospitalDialog hospital={hospital} onDone={invalidateHospitals} />
                              <Button
                                variant="ghost"
                                size="sm"
                                className="rounded-xl text-xs font-semibold tap-feedback"
                                disabled={toggleStatus.isPending}
                                onClick={() => toggleStatus.mutate(hospital)}
                              >
                                {isActive ? "Deactivate" : "Activate"}
                              </Button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </TabsContent>

        {/* Users Management Tab */}
        <TabsContent value="users" className="fade-rise">
          <Panel
            title="User Directory"
            description={`${filteredUsers.length} of ${userList.length} accounts displayed`}
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
                placeholder="Search by name, email, mobile phone…"
                value={userSearch}
                onChange={setUserSearch}
              />
              <Select
                value={roleFilter}
                onValueChange={(value) => setRoleFilter(value as "all" | Role)}
              >
                <SelectTrigger className="h-11 w-full rounded-xl sm:w-52 border-border bg-card text-xs font-semibold shadow-subtle">
                  <SelectValue placeholder="All roles" />
                </SelectTrigger>
                <SelectContent className="rounded-xl">
                  <SelectItem value="all">All Roles ({userList.length})</SelectItem>
                  <SelectItem value="customer">Patients</SelectItem>
                  <SelectItem value="doctor">Physicians</SelectItem>
                  <SelectItem value="hospital_manager">Hospital Managers</SelectItem>
                  <SelectItem value="super_admin">Super Administrators</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {users.isLoading ? (
              <LoadingRows rows={4} />
            ) : users.isError ? (
              <ErrorNote
                message={
                  users.error instanceof Error ? users.error.message : "Could not load users"
                }
                onRetry={() => users.refetch()}
              />
            ) : filteredUsers.length === 0 ? (
              <EmptyState
                title="No matching accounts"
                description="Adjust your search query or role filter."
              />
            ) : (
              <div className="overflow-x-auto rounded-2xl border border-border/60">
                <table className="w-full min-w-[740px] text-sm text-left">
                  <thead className="bg-surface border-b border-border/60 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                    <tr>
                      <th className="py-3.5 px-4">Name</th>
                      <th className="py-3.5 px-4">Role</th>
                      <th className="py-3.5 px-4">Contact</th>
                      <th className="py-3.5 px-4">Branch Affiliation</th>
                      <th className="py-3.5 px-4">Status</th>
                      <th className="py-3.5 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/50 bg-card">
                    {filteredUsers.map((u) => (
                      <tr key={u.id} className="transition-colors hover:bg-surface/50">
                        <td className="py-3.5 px-4 font-bold text-foreground">{personName(u)}</td>
                        <td className="py-3.5 px-4 text-xs font-medium text-muted-foreground">
                          {ROLE_LABEL[u.role] ?? u.role}
                        </td>
                        <td className="py-3.5 px-4 text-xs text-muted-foreground">
                          <p className="break-all">{u.email}</p>
                          <p>{u.mobile}</p>
                        </td>
                        <td className="py-3.5 px-4 text-xs font-medium text-foreground">
                          {hospitalList.find((h) => String(h.id) === String(u.hospital_id))?.name ??
                            (u.hospital_id ? `#${u.hospital_id}` : "—")}
                        </td>
                        <td className="py-3.5 px-4 whitespace-nowrap">
                          <StatusBadge status={u.is_active === false ? "inactive" : "active"} />
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="rounded-xl text-xs font-semibold text-destructive hover:bg-destructive/10 hover:text-destructive tap-feedback"
                            disabled={u.is_active === false || deactivate.isPending}
                            onClick={() => deactivate.mutate(u.id)}
                          >
                            Deactivate
                          </Button>
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
        className={`${fieldInputClass} pl-10 h-11 text-xs`}
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
      editing && hospital
        ? adminApi.updateHospital(hospital.id, body)
        : adminApi.createHospital(body),
    onSuccess: () => {
      toast.success(editing ? "Hospital branch updated" : "Hospital branch registered");
      setOpen(false);
      onDone();
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Something went wrong"),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {editing ? (
          <Button
            variant="ghost"
            size="sm"
            className="rounded-xl text-xs font-semibold tap-feedback"
          >
            <Edit2 className="mr-1.5 h-3.5 w-3.5" /> Edit
          </Button>
        ) : (
          <Button size="sm" className="rounded-xl font-semibold shadow-soft tap-feedback">
            <Plus className="mr-1.5 h-4 w-4" /> New Hospital Branch
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="rounded-2xl sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-display text-lg font-bold">
            {editing ? "Edit Hospital Branch" : "Register Hospital Branch"}
          </DialogTitle>
        </DialogHeader>
        <form
          className="grid gap-4 sm:grid-cols-2 pt-2"
          onSubmit={(event) => {
            event.preventDefault();
            setError("");
            if (form.name.trim().length < 2) {
              setError("Hospital branch name is required");
              return;
            }
            mutation.mutate(form);
          }}
        >
          <Field id="h-name" label="Branch Name *" className="sm:col-span-2">
            <Input
              id="h-name"
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
              className={fieldInputClass}
              required
            />
          </Field>
          <Field id="h-city" label="City *">
            <Input
              id="h-city"
              value={form.city}
              onChange={(e) => setForm((p) => ({ ...p, city: e.target.value }))}
              className={fieldInputClass}
              required
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
          <Field id="h-phone" label="Telephone">
            <Input
              id="h-phone"
              value={form.contact_phone}
              onChange={(e) => setForm((p) => ({ ...p, contact_phone: e.target.value }))}
              className={fieldInputClass}
            />
          </Field>
          <Field id="h-email" label="Email Address">
            <Input
              id="h-email"
              type="email"
              value={form.contact_email}
              onChange={(e) => setForm((p) => ({ ...p, contact_email: e.target.value }))}
              className={fieldInputClass}
            />
          </Field>
          <Field id="h-address" label="Street Address" className="sm:col-span-2">
            <Input
              id="h-address"
              value={form.address}
              onChange={(e) => setForm((p) => ({ ...p, address: e.target.value }))}
              className={fieldInputClass}
            />
          </Field>
          {error ? (
            <div className="sm:col-span-2">
              <ErrorNote message={error} />
            </div>
          ) : null}
          <DialogFooter className="sm:col-span-2 pt-2">
            <Button
              type="submit"
              className="rounded-xl font-semibold shadow-soft tap-feedback"
              disabled={mutation.isPending}
            >
              {mutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              {editing ? "Save Changes" : "Register Branch"}
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
      toast.success(kind === "manager" ? "Hospital Manager created" : "Physician account created");
      setOpen(false);
      setForm({
        first_name: "",
        last_name: "",
        email: "",
        mobile: "",
        password: "",
        hospital_id: "",
      });
      onDone();
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Something went wrong"),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          size="sm"
          variant={kind === "manager" ? "outline" : "default"}
          className="rounded-xl text-xs font-semibold tap-feedback"
        >
          <UserPlus className="mr-1.5 h-3.5 w-3.5" /> New{" "}
          {kind === "manager" ? "Manager" : "Doctor"}
        </Button>
      </DialogTrigger>
      <DialogContent className="rounded-2xl sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-display text-lg font-bold">
            Create {kind === "manager" ? "Hospital Manager" : "Specialist Physician"}
          </DialogTitle>
        </DialogHeader>
        <form
          className="grid gap-4 sm:grid-cols-2 pt-2"
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
              setError("Select an assigned hospital branch");
              return;
            }

            const rawMobile = form.mobile.replace(/[\s\-\.\(\)]/g, "");
            const normalizedMobile = rawMobile.startsWith("+91")
              ? rawMobile
              : rawMobile.length === 10
                ? `+91${rawMobile}`
                : form.mobile.trim();

            mutation.mutate({
              first_name: form.first_name.trim(),
              last_name: form.last_name.trim(),
              email: form.email.trim(),
              mobile: normalizedMobile,
              password: form.password,
              hospital_id: Number.isNaN(Number(form.hospital_id))
                ? form.hospital_id
                : Number(form.hospital_id),
            });
          }}
        >
          <Field id={`${kind}-first`} label="First Name *">
            <Input
              id={`${kind}-first`}
              value={form.first_name}
              onChange={(e) => setForm((p) => ({ ...p, first_name: e.target.value }))}
              className={fieldInputClass}
              required
            />
          </Field>
          <Field id={`${kind}-last`} label="Last Name *">
            <Input
              id={`${kind}-last`}
              value={form.last_name}
              onChange={(e) => setForm((p) => ({ ...p, last_name: e.target.value }))}
              className={fieldInputClass}
              required
            />
          </Field>
          <Field id={`${kind}-email`} label="Email Address *" className="sm:col-span-2">
            <Input
              id={`${kind}-email`}
              type="email"
              value={form.email}
              onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))}
              className={fieldInputClass}
              required
            />
          </Field>
          <Field id={`${kind}-mobile`} label="Mobile Number">
            <Input
              id={`${kind}-mobile`}
              value={form.mobile}
              onChange={(e) => setForm((p) => ({ ...p, mobile: e.target.value }))}
              className={fieldInputClass}
            />
          </Field>
          <Field id={`${kind}-password`} label="Temporary Password *">
            <Input
              id={`${kind}-password`}
              type="password"
              value={form.password}
              onChange={(e) => setForm((p) => ({ ...p, password: e.target.value }))}
              className={fieldInputClass}
              required
            />
          </Field>
          <div className="space-y-1.5 sm:col-span-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Assigned Hospital Branch *
            </label>
            <Select
              value={form.hospital_id}
              onValueChange={(value) => setForm((p) => ({ ...p, hospital_id: value }))}
            >
              <SelectTrigger className="h-11 rounded-xl border-border bg-background">
                <SelectValue placeholder="Select hospital branch" />
              </SelectTrigger>
              <SelectContent className="rounded-xl">
                {hospitals.map((hospital) => (
                  <SelectItem key={hospital.id} value={String(hospital.id)}>
                    {hospital.name} ({hospital.city})
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
          <DialogFooter className="sm:col-span-2 pt-2">
            <Button
              type="submit"
              className="rounded-xl font-semibold shadow-soft tap-feedback"
              disabled={mutation.isPending}
            >
              {mutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Create {kind === "manager" ? "Manager Account" : "Physician Account"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
