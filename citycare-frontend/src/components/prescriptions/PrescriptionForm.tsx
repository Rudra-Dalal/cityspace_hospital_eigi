import { useState } from "react";
import { Minus, Plus } from "lucide-react";
import { toast } from "sonner";
import { prescriptionsApi, type Medicine } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
const blank = (): Medicine => ({ name: "", dosage: "", frequency: "", duration: "", instructions: "" });
export function PrescriptionForm({ appointmentId, onDone }: { appointmentId: string; onDone: () => void }) {
  const [diagnosis, setDiagnosis] = useState(""); const [instructions, setInstructions] = useState(""); const [medicines, setMedicines] = useState<Medicine[]>([blank()]); const [saving, setSaving] = useState(false);
  const update = (index: number, key: keyof Medicine, value: string) => setMedicines((all) => all.map((m, i) => i === index ? { ...m, [key]: value } : m));
  async function submit() { setSaving(true); try { await prescriptionsApi.create({ appointment_id: appointmentId, diagnosis, medicines, general_instructions: instructions }); toast.success("Prescription created and PDF uploaded"); onDone(); } catch (e) { toast.error(e instanceof Error ? e.message : "Could not create prescription"); } finally { setSaving(false); } }
  return <div className="mt-4 space-y-3 rounded-xl border border-border bg-card p-4"><Input value={diagnosis} onChange={(e) => setDiagnosis(e.target.value)} placeholder="Diagnosis" />
    {medicines.map((medicine, index) => <div key={index} className="grid gap-2 sm:grid-cols-2"><Input value={medicine.name} onChange={(e) => update(index, "name", e.target.value)} placeholder="Medicine name" /><Input value={medicine.dosage} onChange={(e) => update(index, "dosage", e.target.value)} placeholder="Dosage" /><Input value={medicine.frequency} onChange={(e) => update(index, "frequency", e.target.value)} placeholder="Frequency" /><Input value={medicine.duration} onChange={(e) => update(index, "duration", e.target.value)} placeholder="Duration" /><Input value={medicine.instructions} onChange={(e) => update(index, "instructions", e.target.value)} placeholder="Instructions" /><Button type="button" variant="ghost" disabled={medicines.length === 1} onClick={() => setMedicines((all) => all.filter((_, i) => i !== index))}><Minus className="mr-1 h-4 w-4" /> Remove</Button></div>)}
    <Button type="button" variant="outline" onClick={() => setMedicines((all) => [...all, blank()])}><Plus className="mr-1 h-4 w-4" /> Add medicine</Button><Textarea value={instructions} onChange={(e) => setInstructions(e.target.value)} placeholder="General instructions" />
    <Button onClick={() => void submit()} disabled={saving}>{saving ? "Creating…" : "Create prescription"}</Button></div>;
}
