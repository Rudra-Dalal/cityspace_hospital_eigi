import { useState } from "react";
import { Bot, Send } from "lucide-react";
import { patientAiApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui-kit";

export function PatientPrescriptionChat() {
  const [message, setMessage] = useState("");
  const [reply, setReply] = useState("");
  const [loading, setLoading] = useState(false);
  async function ask() {
    if (!message.trim()) return;
    setLoading(true);
    try { setReply((await patientAiApi.chat({ message })).reply); }
    catch (error) { setReply(error instanceof Error ? error.message : "Could not contact the assistant."); }
    finally { setLoading(false); }
  }
  return <Panel title="Prescription assistant" description="Ask about information already present in your prescriptions.">
    <div className="flex gap-2"><Input value={message} onChange={(e) => setMessage(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") void ask(); }} placeholder="What medicines did my doctor prescribe?" />
      <Button onClick={() => void ask()} disabled={loading}><Send className="mr-2 h-4 w-4" />{loading ? "Asking…" : "Ask"}</Button></div>
    {reply ? <div className="mt-4 rounded-xl bg-surface p-4 text-sm"><Bot className="mr-2 inline h-4 w-4 text-primary" />{reply}</div> : null}
  </Panel>;
}
