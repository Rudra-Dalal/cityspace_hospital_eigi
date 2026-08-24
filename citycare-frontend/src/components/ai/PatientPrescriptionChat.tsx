import { useState } from "react";
import { Bot, Send, Sparkles, Loader2, HelpCircle } from "lucide-react";
import { patientAiApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui-kit";

const SUGGESTIONS = [
  "What medicines did my doctor prescribe?",
  "How often should I take my medications?",
  "Are there any specific dietary instructions?",
];

export function PatientPrescriptionChat() {
  const [message, setMessage] = useState("");
  const [reply, setReply] = useState("");
  const [loading, setLoading] = useState(false);

  async function ask(queryText?: string) {
    const textToSend = (queryText || message).trim();
    if (!textToSend) return;
    if (queryText) setMessage(queryText);
    setLoading(true);
    try {
      const res = await patientAiApi.chat({ message: textToSend });
      setReply(res.reply);
    } catch (error) {
      setReply(error instanceof Error ? error.message : "Could not contact the health assistant.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Panel
      title="AI Prescription & Health Assistant"
      description="Instant answers regarding dosage, schedules, and guidance extracted from your verified prescriptions."
    >
      <div className="space-y-4">
        {/* Suggested Prompts */}
        <div className="flex flex-wrap gap-1.5">
          {SUGGESTIONS.map((sug) => (
            <button
              key={sug}
              type="button"
              onClick={() => ask(sug)}
              className="rounded-full border border-border/80 bg-secondary/50 px-3 py-1 text-[11px] font-medium text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors tap-feedback"
            >
              {sug}
            </button>
          ))}
        </div>

        {/* Input Form */}
        <div className="flex gap-2">
          <Input
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void ask();
            }}
            placeholder="Ask about your prescribed medicines, dosage instructions…"
            className="rounded-xl h-11 border-border bg-background text-sm"
          />
          <Button
            onClick={() => void ask()}
            disabled={loading || !message.trim()}
            className="rounded-xl font-semibold shadow-soft tap-feedback h-11 px-5"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                <Send className="mr-1.5 h-4 w-4" /> Ask
              </>
            )}
          </Button>
        </div>

        {/* Response Bubble */}
        {reply ? (
          <div className="rounded-2xl border border-primary/20 bg-primary/5 p-4 sm:p-5 text-sm space-y-2 fade-rise">
            <div className="flex items-center gap-2 text-primary font-bold text-xs">
              <Bot className="h-4 w-4" />
              <span>CityCare Medical AI</span>
            </div>
            <p className="text-foreground leading-relaxed text-xs sm:text-sm whitespace-pre-wrap">
              {reply}
            </p>
            <p className="text-[10px] text-muted-foreground pt-1 border-t border-primary/10">
              Disclaimer: AI responses are for informational purposes only. Consult your doctor for
              personal medical advice.
            </p>
          </div>
        ) : null}
      </div>
    </Panel>
  );
}
