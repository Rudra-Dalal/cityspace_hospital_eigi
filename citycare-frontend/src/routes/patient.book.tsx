import { useState, useMemo } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Loader2,
  TriangleAlert,
  Building2,
  User,
  Calendar as CalendarIcon,
  Clock,
  MapPin,
  Phone,
  Stethoscope,
  ChevronRight,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import { appointmentsApi, patientApi, Hospital, DoctorPublicOut } from "@/lib/api";
import { RoleGate } from "@/components/RoleGate";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field, fieldErrorClass, fieldInputClass } from "@/components/Field";
import { EmptyState, ErrorNote, PageHeader, Panel } from "@/components/ui-kit";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { formatDate, nextDays, toDateKey } from "@/lib/format";

const SYMPTOMS = ["fever", "cough", "cold", "bodyache", "headache", "other"] as const;

export const Route = createFileRoute("/patient/book")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Book an appointment — CityCare" },
      {
        name: "description",
        content: "Select your hospital, choose your specialist doctor, and book an appointment in real-time.",
      },
      { property: "og:title", content: "Book an appointment — CityCare" },
      { property: "og:description", content: "Multi-hospital explicit specialist booking with real-time doctor availability." },
    ],
  }),
  component: () => (
    <RoleGate role="customer">
      <BookAppointment />
    </RoleGate>
  ),
});

function BookAppointment() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const days = useMemo(() => nextDays(7), []);

  // Selection states
  const [selectedHospital, setSelectedHospital] = useState<Hospital | null>(null);
  const [selectedDoctor, setSelectedDoctor] = useState<DoctorPublicOut | null>(null);
  const [specializationFilter, setSpecializationFilter] = useState<string>("all");
  const [date, setDate] = useState(toDateKey(days[0]!));
  const [slot, setSlot] = useState<string | null>(null);
  const [symptoms, setSymptoms] = useState<string[]>([]);
  const [temperature, setTemperature] = useState("");
  const [reason, setReason] = useState("");
  const [errors, setErrors] = useState<{
    hospital?: string;
    doctor?: string;
    slot?: string;
    reason?: string;
    temperature?: string;
    symptoms?: string;
  }>({});
  const [conflict, setConflict] = useState("");
  const [success, setSuccess] = useState<{
    date: string;
    slot: string;
    doctorName?: string;
    hospitalName?: string;
  } | null>(null);

  // 1. Fetch active hospitals
  const hospitalsQuery = useQuery({
    queryKey: ["active-hospitals"],
    queryFn: async () => {
      const data = await patientApi.listHospitals();
      return Array.isArray(data) ? data : [];
    },
  });

  // 2. Fetch doctors for selected hospital
  const doctorsQuery = useQuery({
    queryKey: ["active-doctors", selectedHospital?.id],
    queryFn: async () => {
      if (!selectedHospital?.id) return [];
      const data = await patientApi.listDoctors({ hospital_id: String(selectedHospital.id) });
      return Array.isArray(data) ? data : [];
    },
    enabled: Boolean(selectedHospital?.id),
  });

  // Unique specializations at this hospital
  const specializations = useMemo(() => {
    const list = doctorsQuery.data || [];
    const specs = new Set<string>();
    list.forEach((d) => {
      if (d.specialization) specs.add(d.specialization);
    });
    return Array.from(specs);
  }, [doctorsQuery.data]);

  const filteredDoctors = useMemo(() => {
    const list = doctorsQuery.data || [];
    if (specializationFilter === "all") return list;
    return list.filter((d) => d.specialization === specializationFilter);
  }, [doctorsQuery.data, specializationFilter]);

  // 3. Fetch doctor-specific live availability
  const availabilityQuery = useQuery({
    queryKey: ["doctor-availability", selectedDoctor?.id, date],
    queryFn: async () => {
      if (!selectedDoctor?.id) return null;
      return await patientApi.getDoctorAvailability(String(selectedDoctor.id), date);
    },
    enabled: Boolean(selectedDoctor?.id && date),
  });

  const book = useMutation({
    mutationFn: (payload: {
      hospital_id: string;
      doctor_id: string;
      date: string;
      slot: string;
      reason: string;
      temperature?: number;
      symptoms: string[];
    }) => appointmentsApi.create(payload),
    onSuccess: (_data, variables) => {
      setSuccess({
        date: variables.date,
        slot: variables.slot,
        doctorName: selectedDoctor ? `Dr. ${selectedDoctor.first_name} ${selectedDoctor.last_name}` : undefined,
        hospitalName: selectedHospital ? selectedHospital.name : undefined,
      });
      setConflict("");
      setSlot(null);
      toast.success("Appointment booked successfully!");
      queryClient.invalidateQueries({ queryKey: ["appointments"] });
      queryClient.invalidateQueries({ queryKey: ["doctor-availability", selectedDoctor?.id, variables.date] });
    },
    onError: (error) => {
      const msg = error instanceof Error ? error.message : "Could not book this slot";
      setConflict(msg);
      toast.error(msg);
      queryClient.invalidateQueries({ queryKey: ["doctor-availability", selectedDoctor?.id, date] });
    },
  });

  function toggleSymptom(value: string) {
    setSymptoms((prev) => (prev.includes(value) ? prev.filter((s) => s !== value) : [...prev, value]));
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const next: typeof errors = {};

    if (!selectedHospital) next.hospital = "Please select a hospital";
    if (!selectedDoctor) next.doctor = "Please select a specialist doctor";
    if (!slot) next.slot = "Please select an available time slot";
    if (reason.trim().length < 10) next.reason = "Please provide at least 10 characters describing your symptoms or reason";

    let tempNum: number | undefined = undefined;
    if (temperature.trim()) {
      tempNum = Number(temperature);
      if (Number.isNaN(tempNum) || tempNum < 95 || tempNum > 110) {
        next.temperature = "Enter a valid temperature in °F between 95 and 110";
      }
    }

    setErrors(next);
    setConflict("");
    if (Object.keys(next).length > 0) {
      if (next.hospital) toast.error(next.hospital);
      else if (next.doctor) toast.error(next.doctor);
      else if (next.slot) toast.error(next.slot);
      else if (next.reason) toast.error(next.reason);
      return;
    }

    book.mutate({
      hospital_id: String(selectedHospital!.id),
      doctor_id: String(selectedDoctor!.id),
      date,
      slot: slot!,
      reason: reason.trim(),
      temperature: tempNum,
      symptoms,
    });
  }

  if (success) {
    return (
      <>
        <PageHeader eyebrow="Confirmed" title="Your appointment is booked!" />
        <Panel className="mx-auto max-w-xl text-center shadow-lg border-primary/20">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-success/15">
            <CheckCircle2 className="h-10 w-10 text-success" />
          </div>
          <h2 className="mt-5 font-display text-2xl leading-tight">Appointment Confirmed</h2>
          <p className="mt-2 text-base text-foreground font-medium">
            {success.doctorName} • {success.hospitalName}
          </p>
          <div className="mt-4 rounded-xl bg-accent/50 p-4 text-sm">
            <p className="font-semibold text-foreground">{formatDate(success.date)}</p>
            <p className="text-muted-foreground mt-1">Time Slot: {success.slot}</p>
          </div>
          <div className="mt-7 flex flex-wrap justify-center gap-3">
            <Button className="rounded-xl" onClick={() => navigate({ to: "/patient/dashboard" })}>
              View my appointments
            </Button>
            <Button
              variant="outline"
              className="rounded-xl"
              onClick={() => {
                setSuccess(null);
                setSelectedHospital(null);
                setSelectedDoctor(null);
                setSlot(null);
                setReason("");
                setTemperature("");
                setSymptoms([]);
              }}
            >
              Book another visit
            </Button>
          </div>
        </Panel>
      </>
    );
  }

  return (
    <div className="space-y-8 max-w-6xl mx-auto pb-12">
      <PageHeader
        eyebrow="Explicit Specialist Booking"
        title="Book a Medical Consultation"
        description="Choose your preferred hospital, select a specialized physician, and pick an available time slot."
      />

      <form onSubmit={handleSubmit} className="space-y-8" noValidate>
        {/* STEP 1: Select Active Hospital */}
        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
              1
            </span>
            <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
              <Building2 className="h-5 w-5 text-primary" />
              Select Hospital / Clinic Branch
            </h2>
          </div>

          {hospitalsQuery.isLoading ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-32 rounded-2xl" />
              ))}
            </div>
          ) : hospitalsQuery.isError ? (
            <ErrorNote message="Failed to load hospitals. Please refresh the page." />
          ) : (hospitalsQuery.data || []).length === 0 ? (
            <EmptyState title="No active hospitals found" description="Please contact administrator." />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {(hospitalsQuery.data || []).map((h) => {
                const isSelected = selectedHospital?.id === h.id;
                return (
                  <button
                    key={String(h.id)}
                    type="button"
                    onClick={() => {
                      if (selectedHospital?.id !== h.id) {
                        setSelectedHospital(h);
                        setSelectedDoctor(null);
                        setSlot(null);
                        setErrors((prev) => ({ ...prev, hospital: undefined, doctor: undefined }));
                      }
                    }}
                    className={cn(
                      "relative rounded-2xl p-5 text-left transition-all duration-200 border",
                      isSelected
                        ? "border-primary bg-primary/5 ring-2 ring-primary shadow-soft"
                        : "border-border bg-card hover:border-border/80 hover:bg-accent/40 hover:-translate-y-0.5",
                    )}
                  >
                    <div className="flex items-start justify-between">
                      <h3 className="font-semibold text-base text-foreground leading-snug">{h.name}</h3>
                      {isSelected ? (
                        <CheckCircle2 className="h-5 w-5 text-primary shrink-0 ml-2" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0 ml-2 mt-0.5 opacity-50" />
                      )}
                    </div>
                    <p className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
                      <MapPin className="h-3.5 w-3.5 shrink-0" />
                      <span>{h.address ? `${h.address}, ${h.city || ""}` : h.city || "Branch Location"}</span>
                    </p>
                    {h.contact_phone ? (
                      <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
                        <Phone className="h-3.5 w-3.5 shrink-0" />
                        <span>{h.contact_phone}</span>
                      </p>
                    ) : null}
                    {h.facilities && h.facilities.length > 0 ? (
                      <div className="mt-3 flex flex-wrap gap-1">
                        {h.facilities.slice(0, 3).map((f) => (
                          <span
                            key={f}
                            className="inline-block rounded-md bg-accent px-2 py-0.5 text-[10px] font-medium text-foreground/80"
                          >
                            {f}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </button>
                );
              })}
            </div>
          )}
          {errors.hospital ? <p className="text-xs font-medium text-destructive">{errors.hospital}</p> : null}
        </section>

        {/* STEP 2: Select Doctor */}
        {selectedHospital ? (
          <section className="space-y-4 pt-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
                  2
                </span>
                <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
                  <Stethoscope className="h-5 w-5 text-primary" />
                  Select Specialist Doctor at {selectedHospital.name}
                </h2>
              </div>

              {specializations.length > 1 ? (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground hidden sm:inline">Filter:</span>
                  <select
                    value={specializationFilter}
                    onChange={(e) => setSpecializationFilter(e.target.value)}
                    className="rounded-xl border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground"
                  >
                    <option value="all">All Specializations ({specializations.length})</option>
                    {specializations.map((spec) => (
                      <option key={spec} value={spec}>
                        {spec}
                      </option>
                    ))}
                  </select>
                </div>
              ) : null}
            </div>

            {doctorsQuery.isLoading ? (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {[1, 2].map((i) => (
                  <Skeleton key={i} className="h-28 rounded-2xl" />
                ))}
              </div>
            ) : filteredDoctors.length === 0 ? (
              <EmptyState
                title="No active doctors available"
                description={`No active physicians currently available at ${selectedHospital.name}.`}
              />
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {filteredDoctors.map((doc) => {
                  const isSelected = selectedDoctor?.id === doc.id;
                  return (
                    <button
                      key={String(doc.id)}
                      type="button"
                      onClick={() => {
                        setSelectedDoctor(doc);
                        setSlot(null);
                        setErrors((prev) => ({ ...prev, doctor: undefined }));
                      }}
                      className={cn(
                        "relative rounded-2xl p-5 text-left transition-all duration-200 border",
                        isSelected
                          ? "border-primary bg-primary/5 ring-2 ring-primary shadow-soft"
                          : "border-border bg-card hover:border-border/80 hover:bg-accent/40 hover:-translate-y-0.5",
                      )}
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <h3 className="font-semibold text-base text-foreground leading-snug">
                            Dr. {doc.first_name} {doc.last_name}
                          </h3>
                          <p className="text-xs font-medium text-primary mt-0.5">{doc.specialization}</p>
                        </div>
                        {isSelected ? (
                          <CheckCircle2 className="h-5 w-5 text-primary shrink-0 ml-2" />
                        ) : (
                          <User className="h-5 w-5 text-muted-foreground shrink-0 ml-2 opacity-40" />
                        )}
                      </div>
                      <p className="mt-2 text-xs text-muted-foreground">{doc.qualification}</p>
                      <div className="mt-3 flex items-center justify-between text-[11px] text-muted-foreground/80 border-t border-border/50 pt-2">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {doc.working_hours || "10:00 - 20:00"}
                        </span>
                        <span className="truncate max-w-[120px]">
                          {doc.available_days?.join(", ") || "Mon - Sat"}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
            {errors.doctor ? <p className="text-xs font-medium text-destructive">{errors.doctor}</p> : null}
          </section>
        ) : null}

        {/* STEP 3 & 4: Date, Live Doctor Slots & Consultation Details */}
        {selectedDoctor ? (
          <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr] pt-2">
            <div className="space-y-6">
              <Panel
                title="3. Choose Appointment Date"
                description="Select any day in the next 7-day booking window"
              >
                <div className="grid grid-cols-3 gap-2.5 sm:grid-cols-4 lg:grid-cols-7">
                  {days.map((day, index) => {
                    const key = toDateKey(day);
                    const active = key === date;
                    return (
                      <button
                        key={key}
                        type="button"
                        onClick={() => {
                          setDate(key);
                          setSlot(null);
                          setConflict("");
                        }}
                        className={cn(
                          "rounded-xl px-2 py-3 text-center transition-all duration-200 border",
                          active
                            ? "border-primary bg-primary text-primary-foreground shadow-soft"
                            : "border-border bg-card text-foreground hover:-translate-y-0.5 hover:bg-accent",
                        )}
                      >
                        <span className="block text-[11px] font-semibold uppercase tracking-wide opacity-75">
                          {index === 0 ? "Today" : day.toLocaleDateString(undefined, { weekday: "short" })}
                        </span>
                        <span className="mt-1 block font-display text-lg leading-none">{day.getDate()}</span>
                        <span className="mt-1 block text-[11px] opacity-70">
                          {day.toLocaleDateString(undefined, { month: "short" })}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </Panel>

              <Panel
                title="Available Slots"
                description={`Dr. ${selectedDoctor.first_name} ${selectedDoctor.last_name} • ${formatDate(date)}`}
              >
                {availabilityQuery.isLoading ? (
                  <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
                    {Array.from({ length: 6 }).map((_, i) => (
                      <Skeleton key={i} className="h-12 rounded-xl" />
                    ))}
                  </div>
                ) : availabilityQuery.isError ? (
                  <ErrorNote
                    message={
                      availabilityQuery.error instanceof Error
                        ? availabilityQuery.error.message
                        : "Could not load doctor availability"
                    }
                  />
                ) : !availabilityQuery.data?.is_available ? (
                  <EmptyState
                    title="Doctor Not Available"
                    description={`Dr. ${selectedDoctor.first_name} is not on duty on ${availabilityQuery.data?.day_of_week || "this day"}. Please select another date.`}
                  />
                ) : (availabilityQuery.data.available_slots || []).length === 0 ? (
                  <EmptyState
                    title="All Slots Booked"
                    description="All appointment slots for this doctor on this day are currently booked. Please choose another day."
                  />
                ) : (
                  <>
                    <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
                      {(availabilityQuery.data.available_slots || []).map((value) => {
                        const active = value === slot;
                        return (
                          <button
                            key={value}
                            type="button"
                            onClick={() => {
                              setSlot(value);
                              setErrors((prev) => ({ ...prev, slot: undefined }));
                            }}
                            className={cn(
                              "rounded-xl px-3 py-3 text-sm font-semibold transition-all duration-200 border",
                              active
                                ? "border-primary bg-primary text-primary-foreground shadow-soft scale-[1.02]"
                                : "border-border bg-card text-foreground hover:-translate-y-0.5 hover:bg-accent",
                            )}
                          >
                            {value}
                          </button>
                        );
                      })}
                    </div>
                    {errors.slot ? <p className="mt-3 text-xs font-medium text-destructive">{errors.slot}</p> : null}
                  </>
                )}
              </Panel>
            </div>

            {/* Medical details form */}
            <div className="space-y-6">
              <Panel title="4. Consultation Details">
                <div className="space-y-5">
                  <div className="space-y-2">
                    <p className="text-sm font-medium">Select Symptoms (Optional)</p>
                    <div className="flex flex-wrap gap-2">
                      {SYMPTOMS.map((symptom) => {
                        const active = symptoms.includes(symptom);
                        return (
                          <button
                            key={symptom}
                            type="button"
                            onClick={() => toggleSymptom(symptom)}
                            className={cn(
                              "rounded-full px-4 py-1.5 text-xs font-medium capitalize transition-all duration-200 border",
                              active
                                ? "border-primary bg-primary text-primary-foreground shadow-soft"
                                : "border-border bg-card text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                            )}
                          >
                            {symptom}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <Field id="temperature" label="Body Temperature (°F, optional)" error={errors.temperature}>
                    <Input
                      id="temperature"
                      inputMode="decimal"
                      placeholder="e.g. 98.6"
                      value={temperature}
                      onChange={(e) => setTemperature(e.target.value)}
                      className={cn(fieldInputClass, errors.temperature && fieldErrorClass)}
                    />
                  </Field>

                  <Field id="reason" label="Reason for Visit / Symptoms *" error={errors.reason}>
                    <Textarea
                      id="reason"
                      rows={4}
                      placeholder="Please describe what you are experiencing (at least 10 characters)…"
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      maxLength={1000}
                      className={cn(
                        "rounded-xl border-border bg-background",
                        errors.reason && fieldErrorClass,
                      )}
                    />
                  </Field>
                </div>
              </Panel>

              {/* Booking Summary Box */}
              <div className="rounded-2xl border border-border/80 bg-accent/30 p-5 space-y-3">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                  <Sparkles className="h-3.5 w-3.5 text-primary" />
                  Booking Summary
                </h4>
                <div className="text-sm space-y-1.5">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Hospital:</span>
                    <span className="font-medium text-foreground">{selectedHospital.name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Doctor:</span>
                    <span className="font-medium text-foreground">
                      Dr. {selectedDoctor.first_name} {selectedDoctor.last_name} ({selectedDoctor.specialization})
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Date & Slot:</span>
                    <span className="font-medium text-foreground">
                      {formatDate(date)} • {slot || "No slot selected"}
                    </span>
                  </div>
                </div>
              </div>

              {conflict ? (
                <div className="flex items-start gap-3 rounded-2xl bg-destructive/15 p-4 text-sm font-medium text-destructive">
                  <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{conflict}</span>
                </div>
              ) : null}

              <Button
                type="submit"
                size="lg"
                className="w-full rounded-xl font-semibold shadow-soft"
                disabled={book.isPending}
              >
                {book.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Confirm Appointment Booking
              </Button>
            </div>
          </div>
        ) : null}
      </form>
    </div>
  );
}
