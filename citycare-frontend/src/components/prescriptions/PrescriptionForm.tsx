import { useState } from "react";
import { Minus, Plus, Stethoscope, FileText, Loader2, Pill, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { prescriptionsApi, type Medicine } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field } from "@/components/Field";

const blank = (): Medicine => ({
  name: "",
  dosage: "",
  frequency: "",
  duration: "",
  instructions: "",
});

export function PrescriptionForm({
  appointmentId,
  onDone,
}: {
  appointmentId: string;
  onDone: () => void;
}) {
  const [diagnosis, setDiagnosis] = useState("");
  const [instructions, setInstructions] = useState("");
  const [medicines, setMedicines] = useState<Medicine[]>([blank()]);
  const [saving, setSaving] = useState(false);

  const update = (index: number, key: keyof Medicine, value: string) =>
    setMedicines((all) => all.map((m, i) => (i === index ? { ...m, [key]: value } : m)));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!diagnosis.trim()) {
      toast.error("Please enter a medical diagnosis");
      return;
    }
    const validMeds = medicines.filter((m) => m.name.trim().length > 0);
    if (validMeds.length === 0) {
      toast.error("Please specify at least one prescribed medicine");
      return;
    }

    setSaving(true);
    try {
      await prescriptionsApi.create({
        appointment_id: appointmentId,
        diagnosis: diagnosis.trim(),
        medicines: validMeds,
        general_instructions: instructions.trim(),
      });
      toast.success("Prescription generated & PDF uploaded to Cloudinary");
      onDone();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not generate prescription");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="mt-4 space-y-5 rounded-2xl border border-primary/20 bg-card p-5 sm:p-6 shadow-soft fade-rise"
    >
      <div className="flex items-center justify-between border-b border-border/50 pb-3">
        <div className="flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded-lg bg-primary/10 text-primary">
            <Stethoscope className="h-4 w-4" />
          </span>
          <h4 className="font-display text-base font-bold text-foreground">
            Issue Medical Prescription
          </h4>
        </div>
        <span className="text-xs text-muted-foreground font-mono">
          Appt #{String(appointmentId).slice(-6)}
        </span>
      </div>

      <div className="space-y-4">
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">
            Clinical Diagnosis *
          </label>
          <Input
            value={diagnosis}
            onChange={(e) => setDiagnosis(e.target.value)}
            placeholder="e.g. Acute Bronchitis, Seasonal Allergic Rhinitis"
            className="rounded-xl h-11 border-border bg-background text-sm font-medium"
            required
          />
        </div>

        {/* Medicines List */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Prescribed Medications
            </label>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setMedicines((all) => [...all, blank()])}
              className="rounded-xl text-xs font-semibold tap-feedback"
            >
              <Plus className="mr-1 h-3.5 w-3.5" /> Add Medicine
            </Button>
          </div>

          <div className="space-y-3">
            {medicines.map((medicine, index) => (
              <div
                key={index}
                className="rounded-xl border border-border/70 bg-surface/60 p-4 space-y-3"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-foreground flex items-center gap-1.5">
                    <Pill className="h-3.5 w-3.5 text-primary" /> Medicine {index + 1}
                  </span>
                  {medicines.length > 1 ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setMedicines((all) => all.filter((_, i) => i !== index))}
                      className="h-7 text-xs text-destructive hover:bg-destructive/10 hover:text-destructive tap-feedback"
                    >
                      <Minus className="mr-1 h-3.5 w-3.5" /> Remove
                    </Button>
                  ) : null}
                </div>

                <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
                  <Input
                    value={medicine.name}
                    onChange={(e) => update(index, "name", e.target.value)}
                    placeholder="Medicine Name (e.g. Amoxicillin)"
                    className="rounded-xl h-10 border-border bg-background text-xs"
                  />
                  <Input
                    value={medicine.dosage}
                    onChange={(e) => update(index, "dosage", e.target.value)}
                    placeholder="Dosage (e.g. 500mg)"
                    className="rounded-xl h-10 border-border bg-background text-xs"
                  />
                  <Input
                    value={medicine.frequency}
                    onChange={(e) => update(index, "frequency", e.target.value)}
                    placeholder="Frequency (e.g. Twice Daily)"
                    className="rounded-xl h-10 border-border bg-background text-xs"
                  />
                  <Input
                    value={medicine.duration}
                    onChange={(e) => update(index, "duration", e.target.value)}
                    placeholder="Duration (e.g. 5 Days)"
                    className="rounded-xl h-10 border-border bg-background text-xs"
                  />
                  <Input
                    value={medicine.instructions}
                    onChange={(e) => update(index, "instructions", e.target.value)}
                    placeholder="Instructions (e.g. After Food)"
                    className="rounded-xl h-10 border-border bg-background text-xs sm:col-span-2"
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">
            General Advice & Instructions
          </label>
          <Textarea
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            placeholder="Hydration, follow-up recommendations, precautions…"
            rows={3}
            className="rounded-xl border-border bg-background text-xs"
          />
        </div>
      </div>

      <div className="flex items-center justify-end gap-2.5 border-t border-border/50 pt-4">
        <Button
          type="button"
          variant="ghost"
          onClick={onDone}
          className="rounded-xl text-xs font-medium tap-feedback"
        >
          Cancel
        </Button>
        <Button
          type="submit"
          disabled={saving}
          className="rounded-xl font-bold shadow-soft tap-feedback"
        >
          {saving ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <FileText className="mr-2 h-4 w-4" />
          )}
          {saving ? "Generating PDF & Uploading…" : "Save & Issue Prescription"}
        </Button>
      </div>
    </form>
  );
}
