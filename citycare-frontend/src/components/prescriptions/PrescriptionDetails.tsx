import type { Prescription } from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { PrescriptionDownloadButton } from "@/components/prescriptions/PrescriptionDownloadButton";
import { formatDate } from "@/lib/format";

function Detail({ label, value }: { label: string; value?: string | null | undefined }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wider text-muted-foreground">{label}</dt>
      <dd className="mt-1 font-medium">{value || "—"}</dd>
    </div>
  );
}

export function PrescriptionDetails({
  prescription,
  open,
  onOpenChange,
}: {
  prescription: Prescription;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const hospital = prescription.hospital;
  const hospitalLine = hospital
    ? [hospital.address, hospital.city, hospital.state].filter(Boolean).join(", ")
    : "";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto rounded-2xl">
        <DialogHeader>
          <DialogTitle className="font-display text-2xl">
            {hospital?.name ?? "Prescription"}
          </DialogTitle>
        </DialogHeader>
        {hospitalLine ? (
          <p className="-mt-2 text-sm text-muted-foreground">{hospitalLine}</p>
        ) : null}

        <dl className="grid gap-4 rounded-xl bg-surface p-4 text-sm sm:grid-cols-2">
          <Detail label="Patient" value={prescription.patient_name} />
          <Detail label="Doctor" value={prescription.doctor_name} />
          <Detail label="Hospital" value={hospital?.name} />
          <Detail
            label="Prescription date"
            value={formatDate(prescription.created_at?.slice(0, 10))}
          />
        </dl>

        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Diagnosis
          </h3>
          <p className="mt-1 text-sm">{prescription.diagnosis}</p>
        </section>

        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Medicines
          </h3>
          <ol className="mt-2 space-y-3">
            {prescription.medicines.map((medicine, index) => (
              <li key={`${medicine.name}-${index}`} className="rounded-xl bg-surface p-4 text-sm">
                <p className="font-medium">
                  {index + 1}. {medicine.name}
                </p>
                <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                  <Detail label="Dosage" value={medicine.dosage} />
                  <Detail label="Frequency" value={medicine.frequency} />
                  <Detail label="Duration" value={medicine.duration} />
                  <Detail label="Instructions" value={medicine.instructions} />
                </dl>
              </li>
            ))}
          </ol>
        </section>

        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            General instructions
          </h3>
          <p className="mt-1 text-sm">{prescription.general_instructions || "—"}</p>
        </section>

        <div className="flex justify-end">
          <PrescriptionDownloadButton prescriptionId={prescription.id} />
        </div>
      </DialogContent>
    </Dialog>
  );
}
