import { useState } from "react";
import { Minus, Plus } from "lucide-react";
import { toast } from "sonner";
import { prescriptionsApi, type Medicine, type Prescription } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { PrescriptionDetails } from "@/components/prescriptions/PrescriptionDetails";
import { PrescriptionDownloadButton } from "@/components/prescriptions/PrescriptionDownloadButton";

const blank = (): Medicine => ({
  name: "",
  dosage: "",
  frequency: "",
  duration: "",
  instructions: "",
});

function firstValidationError(diagnosis: string, medicines: Medicine[]): string | null {
  if (!diagnosis.trim()) return "Enter a diagnosis";
  for (const [index, medicine] of medicines.entries()) {
    for (const field of ["name", "dosage", "frequency", "duration"] as const) {
      if (!medicine[field].trim()) return `Medicine ${index + 1}: ${field} is required`;
    }
  }
  return null;
}

export function PrescriptionForm({
  appointmentId,
  patientName,
  onDone,
}: {
  appointmentId: string;
  patientName?: string | null;
  onDone: () => void;
}) {
  const [diagnosis, setDiagnosis] = useState("");
  const [instructions, setInstructions] = useState("");
  const [medicines, setMedicines] = useState<Medicine[]>([blank()]);
  const [saving, setSaving] = useState(false);
  const [created, setCreated] = useState<Prescription | null>(null);
  const [viewing, setViewing] = useState(false);

  const update = (index: number, key: keyof Medicine, value: string) =>
    setMedicines((all) => all.map((m, i) => (i === index ? { ...m, [key]: value } : m)));

  async function submit() {
    const error = firstValidationError(diagnosis, medicines);
    if (error) {
      toast.error(error);
      return;
    }
    setSaving(true);
    try {
      const prescription = await prescriptionsApi.create({
        appointment_id: appointmentId,
        diagnosis,
        medicines,
        general_instructions: instructions,
      });
      setCreated(prescription);
      toast.success("Prescription created and PDF uploaded");
      onDone();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not create prescription");
    } finally {
      setSaving(false);
    }
  }

  if (created) {
    return (
      <div className="mt-4 space-y-3 rounded-xl border border-border bg-card p-4">
        <p className="text-sm font-medium">Prescription created successfully.</p>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={() => setViewing(true)}>
            View prescription
          </Button>
          <PrescriptionDownloadButton prescriptionId={created.id} />
        </div>
        <PrescriptionDetails prescription={created} open={viewing} onOpenChange={setViewing} />
      </div>
    );
  }

  return (
    <div className="mt-4 space-y-3 rounded-xl border border-border bg-card p-4">
      {patientName ? (
        <div>
          <p className="text-xs uppercase tracking-wider text-muted-foreground">Patient</p>
          <p className="font-medium">{patientName}</p>
        </div>
      ) : null}
      <Input
        value={diagnosis}
        onChange={(e) => setDiagnosis(e.target.value)}
        placeholder="Diagnosis"
      />
      {medicines.map((medicine, index) => (
        <div key={index} className="grid gap-2 sm:grid-cols-2">
          <Input
            value={medicine.name}
            onChange={(e) => update(index, "name", e.target.value)}
            placeholder="Medicine name"
          />
          <Input
            value={medicine.dosage}
            onChange={(e) => update(index, "dosage", e.target.value)}
            placeholder="Dosage"
          />
          <Input
            value={medicine.frequency}
            onChange={(e) => update(index, "frequency", e.target.value)}
            placeholder="Frequency"
          />
          <Input
            value={medicine.duration}
            onChange={(e) => update(index, "duration", e.target.value)}
            placeholder="Duration"
          />
          <Input
            value={medicine.instructions}
            onChange={(e) => update(index, "instructions", e.target.value)}
            placeholder="Instructions"
          />
          <Button
            type="button"
            variant="ghost"
            disabled={medicines.length === 1}
            onClick={() => setMedicines((all) => all.filter((_, i) => i !== index))}
          >
            <Minus className="mr-1 h-4 w-4" /> Remove
          </Button>
        </div>
      ))}
      <Button
        type="button"
        variant="outline"
        onClick={() => setMedicines((all) => [...all, blank()])}
      >
        <Plus className="mr-1 h-4 w-4" /> Add medicine
      </Button>
      <Textarea
        value={instructions}
        onChange={(e) => setInstructions(e.target.value)}
        placeholder="General instructions"
      />
      <Button onClick={() => void submit()} disabled={saving}>
        {saving ? "Creating…" : "Create prescription"}
      </Button>
    </div>
  );
}
