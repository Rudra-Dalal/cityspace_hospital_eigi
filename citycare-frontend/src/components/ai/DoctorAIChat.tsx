/**
 * Medihub / CityCare Doctor Clinical AI Assistant — complete chat UI
 *
 * DoctorAIChat  (manages state, API calls, conversation)
 *   ├── AIEmptyState  (suggested clinical prompts when no messages)
 *   ├── AIMessage     (individual message bubbles)
 *   ├── AIToolActivity (subtle "Checking today's schedule..." indicator)
 *   └── AIInput       (text input, send button, Enter key handling)
 */

import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import {
  Bot,
  RefreshCcw,
  Send,
  User,
  Loader2,
  CalendarCheck,
  CalendarDays,
  Users,
  BarChart2,
  AlertCircle,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { aiApi, ApiError, type AIChatResponse } from "@/lib/api";
import { Button } from "@/components/ui/button";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type MessageRole = "doctor" | "assistant" | "error";

interface Message {
  id: string;
  role: MessageRole;
  text: string;
  toolActivity?: string[];
}

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

function uid(): string {
  return Math.random().toString(36).slice(2, 10);
}

function friendlyError(err: unknown): string {
  if (err instanceof ApiError) {
    switch (err.status) {
      case 401:
        return "Your clinical session has expired. Please sign in again.";
      case 403:
        return "The AI assistant is only available to verified physicians.";
      case 422:
        return "Invalid message format. Please try again.";
      case 429:
        return "AI rate limit reached. Please try again in a few moments.";
      case 503:
        return "The clinical assistant is temporarily unavailable. Please try again shortly.";
      case 504:
        return "The request timed out. Please try again.";
      default:
        return err.message || "Something went wrong while contacting the AI assistant.";
    }
  }
  return "Unable to connect to the Medihub clinical assistant.";
}

// ---------------------------------------------------------------------------
// AIEmptyState — suggested clinical prompts
// ---------------------------------------------------------------------------

const SUGGESTIONS = [
  {
    icon: <CalendarCheck className="h-4 w-4" />,
    text: "What appointments do I have today?",
  },
  {
    icon: <CalendarDays className="h-4 w-4" />,
    text: "What is my consulting schedule tomorrow?",
  },
  {
    icon: <BarChart2 className="h-4 w-4" />,
    text: "Give me today's clinic attendance metrics.",
  },
  {
    icon: <Users className="h-4 w-4" />,
    text: "Show me my upcoming patient bookings.",
  },
];

function AIEmptyState({ onSelect }: { onSelect: (text: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-5 px-4 py-8 text-center fade-rise">
      <div className="grid h-12 w-12 place-items-center rounded-2xl bg-primary/10 text-primary shadow-subtle border border-primary/20">
        <Bot className="h-6 w-6" />
      </div>
      <div>
        <p className="font-display text-base font-bold text-foreground">Medihub Clinical Assistant</p>
        <p className="mt-1 text-xs text-muted-foreground max-w-xs">
          Query your schedule, review patient rosters, or analyze clinical consultation metrics.
        </p>
      </div>
      <div className="grid w-full max-w-sm gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s.text}
            onClick={() => onSelect(s.text)}
            className="flex items-center gap-2.5 rounded-xl border border-border bg-surface/70 px-3.5 py-2.5 text-left text-xs font-medium text-foreground transition-all hover:border-primary/40 hover:bg-primary/5 tap-feedback"
          >
            <span className="text-primary shrink-0">{s.icon}</span>
            <span className="truncate">{s.text}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AIToolActivity — subtle tool call indicator
// ---------------------------------------------------------------------------

function AIToolActivity({ labels }: { labels: string[] }) {
  if (!labels.length) return null;
  return (
    <div className="flex flex-col gap-1 px-4 py-2">
      {labels.map((label) => (
        <span
          key={label}
          className="inline-flex items-center gap-1.5 text-xs text-primary font-medium"
        >
          <Loader2 className="h-3 w-3 animate-spin" />
          {label}…
        </span>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Markdown-safe text renderer
// ---------------------------------------------------------------------------

function SimpleMarkdown({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <div className="space-y-1 text-xs sm:text-sm leading-relaxed">
      {lines.map((line, i) => {
        const trimmed = line.trim();
        if (!trimmed) return <div key={i} className="h-1.5" />;
        // Bullet list items
        if (/^[-*] /.test(trimmed)) {
          return (
            <div key={i} className="flex gap-2 items-start">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
              <span>{trimmed.slice(2)}</span>
            </div>
          );
        }
        // Numbered list
        if (/^\d+\. /.test(trimmed)) {
          const match = trimmed.match(/^(\d+)\. (.*)$/);
          if (match) {
            return (
              <div key={i} className="flex gap-2 items-start">
                <span className="min-w-[1.25rem] font-semibold text-primary">{match[1]}.</span>
                <span>{match[2]}</span>
              </div>
            );
          }
        }
        // Bold: **text**
        const boldParts = trimmed.split(/\*\*(.*?)\*\*/g);
        return (
          <p key={i}>
            {boldParts.map((part, j) => (j % 2 === 1 ? <strong key={j} className="font-semibold text-foreground">{part}</strong> : part))}
          </p>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// AIMessage — a single chat bubble
// ---------------------------------------------------------------------------

function AIMessage({ message }: { message: Message }) {
  const isDoctor = message.role === "doctor";
  const isError = message.role === "error";

  return (
    <div className={cn("flex gap-2.5", isDoctor ? "flex-row-reverse" : "flex-row")}>
      {/* Avatar */}
      <div
        className={cn(
          "flex h-7 w-7 shrink-0 items-center justify-center rounded-xl text-xs shadow-subtle",
          isDoctor
            ? "bg-primary text-primary-foreground font-bold"
            : isError
              ? "bg-destructive/15 text-destructive"
              : "bg-primary/10 text-primary border border-primary/20",
        )}
      >
        {isDoctor ? (
          <User className="h-3.5 w-3.5" />
        ) : isError ? (
          <AlertCircle className="h-3.5 w-3.5" />
        ) : (
          <Bot className="h-3.5 w-3.5" />
        )}
      </div>

      {/* Bubble */}
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-2.5 text-xs sm:text-sm shadow-subtle",
          isDoctor
            ? "rounded-tr-sm bg-primary text-primary-foreground font-medium"
            : isError
              ? "rounded-tl-sm bg-destructive/10 text-destructive border border-destructive/20"
              : "rounded-tl-sm bg-surface/90 text-foreground border border-border/70",
        )}
      >
        {isDoctor ? (
          <p className="leading-relaxed">{message.text}</p>
        ) : (
          <SimpleMarkdown text={message.text} />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AIInput — message input area
// ---------------------------------------------------------------------------

function AIInput({
  value,
  onChange,
  onSend,
  loading,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  loading: boolean;
}) {
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!loading && value.trim()) {
        onSend();
      }
    }
  };

  return (
    <div className="flex items-end gap-2 border-t border-border/60 bg-card p-3">
      <textarea
        id="ai-chat-input"
        className={cn(
          "flex-1 resize-none rounded-xl border border-border bg-background px-3 py-2 text-xs sm:text-sm outline-none ring-0 transition-colors",
          "placeholder:text-muted-foreground",
          "focus:border-primary focus:ring-1 focus:ring-primary/30",
          "min-h-[38px] max-h-[100px]",
        )}
        placeholder="Query clinic schedule, patient visits, or statistics…"
        rows={1}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={loading}
        aria-label="Message to Clinical AI assistant"
      />
      <Button
        id="ai-chat-send"
        size="icon"
        onClick={onSend}
        disabled={loading || !value.trim()}
        aria-label="Send message"
        className="h-9 w-9 rounded-xl shrink-0 font-semibold shadow-soft tap-feedback"
      >
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// DoctorAIChat — main container
// ---------------------------------------------------------------------------

export function DoctorAIChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [activeTool, setActiveTool] = useState<string[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const userHasScrolledUp = useRef(false);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback((force = false) => {
    if (force || !userHasScrolledUp.current) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, activeTool, scrollToBottom]);

  const handleScroll = () => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    userHasScrolledUp.current = !isNearBottom;
  };

  const handleNewConversation = () => {
    setMessages([]);
    setConversationId(null);
    setInput("");
    setActiveTool([]);
    userHasScrolledUp.current = false;
  };

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    const doctorMessage: Message = { id: uid(), role: "doctor", text };
    setMessages((prev) => [...prev, doctorMessage]);
    setInput("");
    setLoading(true);
    setActiveTool([]);
    userHasScrolledUp.current = false;

    try {
      const data: AIChatResponse = await aiApi.chat({
        message: text,
        conversation_id: conversationId,
      });

      if (data.tool_calls_made?.length) {
        setActiveTool(data.tool_calls_made);
        await new Promise((r) => setTimeout(r, 600));
        setActiveTool([]);
      }

      const assistantMessage: Message = {
        id: uid(),
        role: "assistant",
        text: data.reply,
        toolActivity: data.tool_calls_made,
      };
      setConversationId(data.conversation_id);
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      const errorMessage: Message = {
        id: uid(),
        role: "error",
        text: friendlyError(err),
      };
      setMessages((prev) => [...prev, errorMessage]);
      if (err instanceof ApiError && err.status === 400) {
        setConversationId(null);
      }
    } finally {
      setLoading(false);
      setActiveTool([]);
      scrollToBottom(true);
    }
  }, [input, loading, conversationId, scrollToBottom]);

  const pendingSuggestionRef = useRef<string | null>(null);
  const handleSuggestionClick = (text: string) => {
    pendingSuggestionRef.current = text;
    setInput(text);
  };

  useEffect(() => {
    if (pendingSuggestionRef.current && input === pendingSuggestionRef.current) {
      pendingSuggestionRef.current = null;
      handleSend();
    }
  }, [input, handleSend]);

  return (
    <div className="surface-panel flex h-[560px] flex-col overflow-hidden shadow-subtle border-border/80">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border/60 bg-surface/40 px-5 py-3">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-primary" />
          <h3 className="font-display text-sm font-bold text-foreground">Clinical AI Assistant</h3>
        </div>
        <Button
          id="ai-chat-new"
          variant="ghost"
          size="sm"
          onClick={handleNewConversation}
          title="Start fresh conversation"
          className="h-7 text-xs text-muted-foreground hover:text-foreground tap-feedback"
        >
          <RefreshCcw className="mr-1 h-3 w-3" />
          Reset
        </Button>
      </div>

      {/* Messages area */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-4 py-4 space-y-4"
      >
        {messages.length === 0 ? (
          <AIEmptyState onSelect={handleSuggestionClick} />
        ) : (
          <div className="space-y-3.5">
            {messages.map((msg) => (
              <AIMessage key={msg.id} message={msg} />
            ))}
            {loading && activeTool.length > 0 && <AIToolActivity labels={activeTool} />}
            {loading && activeTool.length === 0 && (
              <div className="flex gap-2.5">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <Bot className="h-3.5 w-3.5" />
                </div>
                <div className="flex items-center gap-1.5 rounded-2xl rounded-tl-sm bg-surface/90 px-3.5 py-2.5 border border-border/70">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:0ms]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:150ms]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:300ms]" />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <AIInput value={input} onChange={setInput} onSend={handleSend} loading={loading} />
    </div>
  );
}
