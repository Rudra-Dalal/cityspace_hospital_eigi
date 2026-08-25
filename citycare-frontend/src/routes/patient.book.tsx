import { useState, useMemo } from "react";
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Loader2,
  AlertCircle,
  Building2,
  User,
  Calendar as CalendarIcon,
  Clock,
  MapPin,
  Phone,
  Stethoscope,
  ChevronRight,
  Sparkles,
  ArrowLeft,
  CalendarCheck,
  ShieldCheck,
  Award,
} from "lucide-react";
import { toast } from "sonner";
import { appointmentsApi, patientApi, Hospital, DoctorPublicOut } from "@/lib/api";
import { RoleGate } from "@/components/RoleGate";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field, fieldErrorClass, fieldInputClass } from "@/components/Field";
import { EmptyState, ErrorNote, PageHeader, Panel, DoctorCardSkeleton } from "@/components/ui-kit";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { formatDate, nextDays, toDateKey } from "@/lib/format";

const SYMPTOMS = [
  "fever",
  "cough",
  "cold",
  "bodyache",
  "headache",
  "fatigue",
  "throat irritation",
  "other",
] as const;

export const Route = createFileRoute("/patient/book")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Book Consultation — Medihub / CityCare" },
      {
        name: "description",
        content:
          "Select your hospital branch, choose your specialist physician, and book an appointment in real-time.",
      },
      { property: "og:title", content: "Book Consultation — Medihub" },
      {
        property: "og:description",
        content: "Multi-hospital specialist booking with real-time doctor availability.",
      },
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
        doctorName: selectedDoctor
          ? `Dr. ${selectedDoctor.first_name} ${selectedDoctor.last_name}`
          : undefined,
        hospitalName: selectedHospital ? selectedHospital.name : undefined,
      });
      setConflict("");
      setSlot(null);
      toast.success("Appointment successfully confirmed");
      queryClient.invalidateQueries({ queryKey: ["appointments"] });
      queryClient.invalidateQueries({
        queryKey: ["doctor-availability", selectedDoctor?.id, variables.date],
      });
    },
    onError: (error) => {
      const msg = error instanceof Error ? error.message : "Could not book this slot";
      setConflict(msg);
      toast.error(msg);
      queryClient.invalidateQueries({
        queryKey: ["doctor-availability", selectedDoctor?.id, date],
      });
    },
  });

  function toggleSymptom(value: string) {
    setSymptoms((prev) =>
      prev.includes(value) ? prev.filter((s) => s !== value) : [...prev, value],
    );
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const next: typeof errors = {};

    if (!selectedHospital) next.hospital = "Please select a hospital branch";
    if (!selectedDoctor) next.doctor = "Please select a specialist doctor";
    if (!slot) next.slot = "Please choose an available time slot";
    if (reason.trim().length < 10)
      next.reason = "Please enter at least 10 characters describing your symptoms or visit purpose";

    let tempNum: number | undefined = undefined;
    if (temperature.trim()) {
      tempNum = Number(temperature);
      if (Number.isNaN(tempNum) || tempNum < 95 || tempNum > 110) {
        next.temperature = "Enter a valid temperature in °F (e.g. 98.6)";
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

  // Calculate current step for progress indicator
  const currentStep = useMemo(() => {
    if (!selectedHospital) return 1;
    if (!selectedDoctor) return 2;
    if (!slot) return 3;
    return 4;
  }, [selectedHospital, selectedDoctor, slot]);

  // Calm, Reassuring Success Screen
  if (success) {
    return (
      <div className="max-w-2xl mx-auto py-8">
        <div className="surface-panel p-8 sm:p-10 text-center space-y-6 shadow-soft border-border/80 fade-rise">
          <div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-success/15 text-success shadow-subtle border border-success/20">
            <CheckCircle2 className="h-10 w-10" />
          </div>

          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-success/10 px-3 py-1 text-xs font-semibold text-success uppercase tracking-wider border border-success/20">
              <ShieldCheck className="h-3.5 w-3.5" /> Confirmed Booking
            </span>
            <h1 className="mt-3 font-display text-2xl sm:text-3xl font-bold tracking-tight text-foreground">
              Consultation Scheduled
            </h1>
            <p className="mt-2 text-sm text-muted-foreground max-w-md mx-auto">
              Your appointment has been registered with the hospital calendar. Please arrive 10 minutes prior to your time slot.
            </p>
          </div>

          {/* Appointment Details Card */}
          <div className="rounded-2xl border border-border/80 bg-surface/70 p-6 text-left space-y-3.5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-border/50 pb-3 gap-1">
              <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Attending Physician
              </span>
              <span className="text-sm font-semibold text-foreground">
                {success.doctorName || "Assigned Specialist"}
              </span>
            </div>

            <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-border/50 pb-3 gap-1">
              <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Hospital Branch
              </span>
              <span className="text-sm font-medium text-foreground">
                {success.hospitalName || "CityCare Branch"}
              </span>
            </div>

            <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-border/50 pb-3 gap-1">
              <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Appointment Date
              </span>
              <span className="text-sm font-medium text-foreground">
                {formatDate(success.date)}
              </span>
            </div>

            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
              <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Confirmed Slot
              </span>
              <span className="text-sm font-bold text-primary">{success.slot}</span>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <Button
              className="w-full sm:w-auto rounded-xl font-semibold shadow-soft tap-feedback h-11 px-6"
              onClick={() => navigate({ to: "/patient/dashboard" })}
            >
              Go to My Appointments
            </Button>
            <Button
              variant="outline"
              className="w-full sm:w-auto rounded-xl font-medium tap-feedback h-11 px-6"
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
              Book Another Visit
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-5xl mx-auto pb-16">
      <PageHeader
        eyebrow="Specialist Booking"
        title="Schedule a Medical Consultation"
        description="Select a verified hospital branch, choose your specialist physician, and confirm a real-time appointment slot."
      />

      {/* 4-Step Progress Indicator */}
      <div className="rounded-2xl border border-border/70 bg-card p-3 sm:p-4 shadow-subtle">
        <div className="grid grid-cols-4 gap-2 text-center">
          {[
            {
              step: 1,
              label: "1. Branch",
              active: Boolean(selectedHospital),
              current: currentStep === 1,
            },
            {
              step: 2,
              label: "2. Physician",
              active: Boolean(selectedDoctor),
              current: currentStep === 2,
            },
            { step: 3, label: "3. Date & Slot", active: Boolean(slot), current: currentStep === 3 },
            {
              step: 4,
              label: "4. Details",
              active: Boolean(slot && reason.length >= 10),
              current: currentStep === 4,
            },
          ].map((item) => (
            <div
              key={item.step}
              className={cn(
                "flex flex-col sm:flex-row items-center justify-center gap-1.5 rounded-xl py-2 px-2 transition-all",
                item.current
                  ? "bg-primary/10 text-primary font-semibold ring-1 ring-primary/30"
                  : item.active
                    ? "bg-secondary/50 text-foreground font-medium"
                    : "text-muted-foreground/60 font-normal",
              )}
            >
              <span
                className={cn(
                  "grid h-5 w-5 place-items-center rounded-full text-[10px] font-bold",
                  item.active
                    ? "bg-primary text-primary-foreground"
                    : item.current
                      ? "bg-primary/20 text-primary"
                      : "bg-muted text-muted-foreground",
                )}
              >
                {item.active ? "✓" : item.step}
              </span>
              <span className="text-xs truncate">{item.label}</span>
            </div>
          ))}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-8" noValidate>
        {/* STEP 1: Select Hospital Branch */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="grid h-7 w-7 place-items-center rounded-xl bg-primary text-xs font-bold text-primary-foreground shadow-subtle">
                1
              </span>
              <h2 className="font-display text-base sm:text-lg font-bold tracking-tight text-foreground flex items-center gap-2">
                <Building2 className="h-5 w-5 text-primary" />
                Select Hospital Branch
              </h2>
            </div>

            {selectedHospital ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="text-xs text-muted-foreground hover:text-foreground tap-feedback"
                onClick={() => {
                  setSelectedHospital(null);
                  setSelectedDoctor(null);
                  setSlot(null);
                }}
              >
                Change Branch
              </Button>
            ) : null}
          </div>

          {hospitalsQuery.isLoading ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-36 rounded-2xl" />
              ))}
            </div>
          ) : hospitalsQuery.isError ? (
            <ErrorNote
              message="Unable to load hospital branches."
              onRetry={() => hospitalsQuery.refetch()}
            />
          ) : (hospitalsQuery.data || []).length === 0 ? (
            <EmptyState
              title="No active hospital branches"
              description="There are currently no active hospital branches registered in the network."
            />
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
                      "group relative rounded-2xl p-5 text-left transition-all duration-200 border tap-feedback",
                      isSelected
                        ? "border-primary bg-card ring-2 ring-primary shadow-soft shadow-primary/10"
                        : "border-border bg-card hover:border-primary/50 hover:bg-card hover:shadow-lg hover:shadow-primary/5 hover:-translate-y-0.5",
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="font-display font-bold text-base text-foreground leading-snug">{h.name}</h3>
                      {isSelected ? (
                        <span className="grid h-6 w-6 place-items-center rounded-full bg-primary text-primary-foreground shrink-0 shadow-subtle">
                          <CheckCircle2 className="h-4 w-4" />
                        </span>
                      ) : (
                        <ChevronRight className="h-4 w-4 text-muted-foreground/50 shrink-0 mt-0.5 group-hover:translate-x-0.5 transition-transform" />
                      )}
                    </div>

                    <p className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
                      <MapPin className="h-3.5 w-3.5 shrink-0 text-primary/70" />
                      <span className="truncate">
                        {h.address ? `${h.address}, ${h.city || ""}` : h.city || "Branch Location"}
                      </span>
                    </p>

                    {h.contact_phone ? (
                      <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
                        <Phone className="h-3.5 w-3.5 shrink-0 text-primary/70" />
                        <span>{h.contact_phone}</span>
                      </p>
                    ) : null}

                    {h.facilities && h.facilities.length > 0 ? (
                      <div className="mt-3.5 flex flex-wrap gap-1 border-t border-border/50 pt-2.5">
                        {h.facilities.slice(0, 3).map((f) => (
                          <span
                            key={f}
                            className="inline-block rounded-md bg-secondary/80 px-2 py-0.5 text-[10px] font-medium text-secondary-foreground"
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
          {errors.hospital ? (
            <p className="text-xs font-semibold text-destructive">{errors.hospital}</p>
          ) : null}
        </section>

        {/* STEP 2: Select Specialist Doctor */}
        {selectedHospital ? (
          <section className="space-y-4 pt-2 fade-rise">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-t border-border/60 pt-6">
              <div className="flex items-center gap-2.5">
                <span className="grid h-7 w-7 place-items-center rounded-xl bg-primary text-xs font-bold text-primary-foreground shadow-subtle">
                  2
                </span>
                <h2 className="font-display text-base sm:text-lg font-bold tracking-tight text-foreground flex items-center gap-2">
                  <Stethoscope className="h-5 w-5 text-primary" />
                  Select Specialist Physician at {selectedHospital.name}
                </h2>
              </div>

              {specializations.length > 1 ? (
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-muted-foreground">Specialty:</span>
                  <select
                    value={specializationFilter}
                    onChange={(e) => setSpecializationFilter(e.target.value)}
                    className="rounded-xl border border-border bg-card px-3 py-1.5 text-xs font-semibold text-foreground shadow-subtle focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
                  >
                    <option value="all">All Specialties ({specializations.length})</option>
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
                  <DoctorCardSkeleton key={i} />
                ))}
              </div>
            ) : doctorsQuery.isError ? (
              <ErrorNote
                message="Unable to load doctors for this branch."
                onRetry={() => doctorsQuery.refetch()}
              />
            ) : filteredDoctors.length === 0 ? (
              <EmptyState
                title="No specialist available"
                description={`No active physicians found matching this specialization at ${selectedHospital.name}.`}
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
                        "group relative rounded-2xl p-5 text-left transition-all duration-200 border tap-feedback",
                        isSelected
                          ? "border-primary bg-card ring-2 ring-primary shadow-soft shadow-primary/10"
                          : "border-border bg-card hover:border-primary/50 hover:bg-card hover:shadow-lg hover:shadow-primary/5 hover:-translate-y-0.5",
                      )}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <h3 className="font-display font-bold text-base text-foreground leading-snug">
                            Dr. {doc.first_name} {doc.last_name}
                          </h3>
                          <span className="inline-block rounded-md bg-primary/10 px-2 py-0.5 text-[11px] font-semibold text-primary mt-1">
                            {doc.specialization}
                          </span>
                        </div>
                        {isSelected ? (
                          <span className="grid h-6 w-6 place-items-center rounded-full bg-primary text-primary-foreground shrink-0 shadow-subtle">
                            <CheckCircle2 className="h-4 w-4" />
                          </span>
                        ) : (
                          <span className="grid h-8 w-8 place-items-center rounded-full bg-secondary/70 text-muted-foreground shrink-0">
                            <User className="h-4 w-4" />
                          </span>
                        )}
                      </div>

                      <p className="mt-2.5 text-xs text-muted-foreground font-medium">
                        {doc.qualification}
                      </p>

                      <div className="mt-3.5 flex items-center justify-between text-[11px] text-muted-foreground border-t border-border/50 pt-2.5">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3 text-primary" />
                          {doc.working_hours || "10:00 - 20:00"}
                        </span>
                        <span className="truncate max-w-[130px] font-medium">
                          {doc.available_days?.join(", ") || "Mon - Sat"}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
            {errors.doctor ? (
              <p className="text-xs font-semibold text-destructive">{errors.doctor}</p>
            ) : null}
          </section>
        ) : null}

        {/* STEP 3 & 4: Date, Live Slot Matrix & Consultation Form */}
        {selectedDoctor ? (
          <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr] pt-2 fade-rise">
            <div className="space-y-6">
              {/* Date Selector */}
              <Panel
                title="3. Choose Appointment Date"
                description="Select any day in the next 7-day booking window"
              >
                <div className="grid grid-cols-4 gap-2 sm:grid-cols-7">
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
                          "flex flex-col items-center justify-center rounded-xl p-2.5 text-center transition-all duration-150 border tap-feedback",
                          active
                            ? "border-primary bg-primary text-primary-foreground shadow-soft ring-1 ring-primary font-semibold"
                            : "border-border bg-card text-foreground hover:border-primary/40 hover:bg-card hover:shadow-subtle font-normal",
                        )}
                      >
                        <span className="block text-[10px] font-medium uppercase tracking-wider opacity-80">
                          {index === 0
                            ? "Today"
                            : day.toLocaleDateString(undefined, { weekday: "short" })}
                        </span>
                        <span className="mt-1 block font-display text-lg font-bold leading-none">
                          {day.getDate()}
                        </span>
                        <span className="mt-1 block text-[10px] opacity-75">
                          {day.toLocaleDateString(undefined, { month: "short" })}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </Panel>

              {/* Available Time Slots */}
              <Panel
                title="Available Time Slots"
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
                    message="Could not load availability for this date."
                    onRetry={() => availabilityQuery.refetch()}
                  />
                ) : !availabilityQuery.data?.is_available ? (
                  <EmptyState
                    title="Clinician Off Duty"
                    description={`Dr. ${selectedDoctor.first_name} is not on duty on ${availabilityQuery.data?.day_of_week || "this day"}. Please select another date.`}
                  />
                ) : (availabilityQuery.data.available_slots || []).length === 0 ? (
                  <EmptyState
                    title="All Slots Booked"
                    description="All consultation slots for this date are booked. Please select another date."
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
                              "rounded-xl px-3 py-2.5 text-xs font-semibold transition-all duration-150 border tap-feedback",
                              active
                                ? "border-primary bg-primary text-primary-foreground shadow-soft ring-2 ring-primary"
                                : "border-border bg-card text-foreground hover:border-primary/40 hover:bg-card hover:shadow-subtle",
                            )}
                          >
                            <span className="flex items-center justify-center gap-1.5">
                              <Clock className="h-3 w-3 opacity-70" />
                              {value}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                    {errors.slot ? (
                      <p className="mt-3 text-xs font-semibold text-destructive">{errors.slot}</p>
                    ) : null}
                  </>
                )}
              </Panel>
            </div>

            {/* Visit Details & Summary Form */}
            <div className="space-y-6">
              <Panel title="4. Consultation Details">
                <div className="space-y-4">
                  <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Reported Symptoms (Optional)
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {SYMPTOMS.map((symptom) => {
                        const active = symptoms.includes(symptom);
                        return (
                          <button
                            key={symptom}
                            type="button"
                            onClick={() => toggleSymptom(symptom)}
                            className={cn(
                              "rounded-full px-3 py-1 text-xs font-medium capitalize transition-all duration-150 border tap-feedback",
                              active
                                ? "border-primary bg-primary text-primary-foreground shadow-subtle font-semibold"
                                : "border-border bg-card text-muted-foreground hover:border-primary/40 hover:bg-card hover:text-foreground",
                            )}
                          >
                            {symptom}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <Field
                    id="temperature"
                    label="Body Temperature (°F, optional)"
                    error={errors.temperature}
                  >
                    <Input
                      id="temperature"
                      inputMode="decimal"
                      placeholder="e.g. 98.6"
                      value={temperature}
                      onChange={(e) => setTemperature(e.target.value)}
                      className={cn(
                        fieldInputClass,
                        errors.temperature && fieldErrorClass,
                        "rounded-xl h-10",
                      )}
                    />
                  </Field>

                  <Field id="reason" label="Visit Reason / Main Symptoms *" error={errors.reason}>
                    <Textarea
                      id="reason"
                      rows={3}
                      placeholder="Please describe your health concern (at least 10 characters)…"
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      maxLength={1000}
                      className={cn(
                        "rounded-xl border-border bg-background text-sm leading-relaxed",
                        errors.reason && fieldErrorClass,
                      )}
                    />
                  </Field>
                </div>
              </Panel>

              {/* Real-time Booking Summary Card */}
              <div className="rounded-2xl border border-border/80 bg-surface/80 p-5 space-y-3.5 shadow-subtle">
                <h4 className="font-display text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                  <Sparkles className="h-3.5 w-3.5 text-primary" />
                  Booking Review Summary
                </h4>
                <div className="text-xs space-y-2 border-t border-border/50 pt-2.5">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Branch:</span>
                    <span className="font-semibold text-foreground">{selectedHospital.name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Specialist:</span>
                    <span className="font-semibold text-foreground">
                      Dr. {selectedDoctor.first_name} {selectedDoctor.last_name} (
                      {selectedDoctor.specialization})
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Date & Slot:</span>
                    <span className="font-bold text-primary">
                      {formatDate(date)} • {slot || "Slot pending"}
                    </span>
                  </div>
                </div>
              </div>

              {conflict ? (
                <div className="flex items-start gap-2.5 rounded-2xl border border-destructive/30 bg-destructive/10 p-4 text-xs font-semibold text-destructive fade-rise">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{conflict}</span>
                </div>
              ) : null}

              <Button
                type="submit"
                size="lg"
                className="w-full rounded-xl font-bold shadow-soft tap-feedback h-11"
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
