import { useState } from "react";
import { Download } from "lucide-react";
import { toast } from "sonner";
import { prescriptionsApi } from "@/lib/api";
import { Button } from "@/components/ui/button";

export function PrescriptionDownloadButton({
  prescriptionId,
  size = "sm",
  variant = "default",
  label = "Download PDF",
}: {
  prescriptionId: string;
  size?: "sm" | "default" | "lg";
  variant?: "default" | "outline" | "ghost";
  label?: string;
}) {
  const [downloading, setDownloading] = useState(false);

  async function download() {
    setDownloading(true);
    try {
      const { blob, filename } = await prescriptionsApi.download(prescriptionId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not download the prescription PDF",
      );
    } finally {
      setDownloading(false);
    }
  }

  return (
    <Button size={size} variant={variant} disabled={downloading} onClick={() => void download()}>
      <Download className="mr-2 h-4 w-4" />
      {downloading ? "Downloading…" : label}
    </Button>
  );
}
