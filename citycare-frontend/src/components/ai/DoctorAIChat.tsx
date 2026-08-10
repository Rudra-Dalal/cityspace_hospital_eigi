/**
 * CityCare Doctor AI Assistant — complete chat UI
 *
 * DoctorAIChat  (manages state, API calls, conversation)
 *   ├── AIEmptyState  (suggested prompts when no messages)
 *   ├── AIMessage     (individual message bubbles)
 *   ├── AIToolActivity (subtle "Checking today's schedule..." indicator)
 *   └── AIInput       (text input, send button, Enter key handling)
 */

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
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
} from "lucide-react";
import { cn } from "@/lib/utils";
import { aiApi, ApiError, type AIChatResponse } from "@/lib/api";

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
        return "Your session has expired. Please sign in again.";
      case 403:
        return "The AI assistant is only available to doctors.";
      case 422:
        return "Invalid message. Please try again.";
      case 429:
        return "You've reached the AI request limit. Please try again shortly.";
      case 503:
        return "The AI assistant is temporarily unavailable. Please try again later.";
      case 504:
        return "The AI request took too long. Please try again.";
      default:
        return err.message || "Something went wrong while contacting the AI assistant.";
    }
  }
  return "Something went wrong while contacting the AI assistant.";
}

// ---------------------------------------------------------------------------
// AIEmptyState — suggested prompts
// ---------------------------------------------------------------------------

const SUGGESTIONS = [
  {
    icon: <CalendarCheck className="h-4 w-4" />,
    text: "What appointments do I have today?",
  },
  {
    icon: <CalendarDays className="h-4 w-4" />,
    text: "What is my schedule tomorrow?",
  },
  {
    icon: <BarChart2 className="h-4 w-4" />,
    text: "Give me today's appointment statistics.",
  },
  {
    icon: <Users className="h-4 w-4" />,
    text: "Show me my upcoming appointments.",
  },
];

function AIEmptyState({ onSelect }: { onSelect: (text: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-6 px-4 py-10 text-center">
      <div className="grid h-14 w-14 place-items-center rounded-2xl bg-primary-soft text-primary">
        <Bot className="h-7 w-7" />
      </div>
      <div>
        <p className="font-display text-lg">CityCare Doctor Assistant</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Ask about your schedule, patients, or appointment statistics.
        </p>
      </div>
      <div className="grid w-full max-w-sm gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s.text}
            onClick={() => onSelect(s.text)}
            className="flex items-center gap-3 rounded-xl border border-border bg-surface px-4 py-3 text-left text-sm text-foreground transition-colors hover:border-primary/40 hover:bg-primary-soft"
          >
            <span className="text-primary">{s.icon}</span>
            {s.text}
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
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground"
        >
          <Loader2 className="h-3 w-3 animate-spin" />
          {label}…
        </span>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Markdown-safe text renderer — splits on newlines and bullet markers
// ---------------------------------------------------------------------------

function SimpleMarkdown({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <div className="space-y-1 text-sm leading-relaxed">
      {lines.map((line, i) => {
        const trimmed = line.trim();
        if (!trimmed) return <div key={i} className="h-2" />;
        // Bullet list items: "- " or "* "
        if (/^[-*] /.test(trimmed)) {
          return (
            <div key={i} className="flex gap-2">
              <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-current opacity-50" />
              <span>{trimmed.slice(2)}</span>
            </div>
          );
        }
        // Numbered list: "1. "
        if (/^\d+\. /.test(trimmed)) {
          const match = trimmed.match(/^(\d+)\. (.*)$/);
          if (match) {
            return (
              <div key={i} className="flex gap-2">
                <span className="min-w-[1.25rem] font-medium">{match[1]}.</span>
                <span>{match[2]}</span>
              </div>
            );
          }
        }
        // Bold: **text**
        const boldParts = trimmed.split(/\*\*(.*?)\*\*/g);
        return (
          <p key={i}>
            {boldParts.map((part, j) =>
              j % 2 === 1 ? <strong key={j}>{part}</strong> : part,
            )}
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
    <div
      className={cn(
        "flex gap-3",
        isDoctor ? "flex-row-reverse" : "flex-row",
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs",
          isDoctor
            ? "bg-primary text-primary-foreground"
            : isError
              ? "bg-destructive/15 text-destructive"
              : "bg-primary-soft text-primary",
        )}
      >
        {isDoctor ? <User className="h-4 w-4" /> : isError ? <AlertCircle className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Bubble */}
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-3",
          isDoctor
            ? "rounded-tr-sm bg-primary text-primary-foreground"
            : isError
              ? "rounded-tl-sm bg-destructive/10 text-destructive"
              : "rounded-tl-sm bg-surface text-foreground",
        )}
      >
        {isDoctor ? (
          <p className="text-sm leading-relaxed">{message.text}</p>
        ) : (
          <SimpleMarkdown text={message.text} />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AIInput — the message input area
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
    <div className="flex items-end gap-2 border-t border-border bg-card px-4 py-3">
      <textarea
        id="ai-chat-input"
        className={cn(
          "flex-1 resize-none rounded-xl border border-input bg-background px-3 py-2 text-sm outline-none ring-0 transition-colors",
          "placeholder:text-muted-foreground",
          "focus:border-primary focus:ring-1 focus:ring-primary/30",
          "min-h-[40px] max-h-[120px]",
        )}
        placeholder="Ask about your schedule, appointments, or patients…"
        rows={1}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={loading}
        aria-label="Message to AI assistant"
        aria-multiline="true"
      />
      <button
        id="ai-chat-send"
        onClick={onSend}
        disabled={loading || !value.trim()}
        aria-label="Send message"
        className={cn(
          "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition-colors",
          loading || !value.trim()
            ? "cursor-not-allowed bg-muted text-muted-foreground"
            : "bg-primary text-primary-foreground hover:bg-primary/90",
        )}
      >
        {loading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Send className="h-4 w-4" />
        )}
      </button>
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

  // Auto-scroll — only if user hasn't scrolled up
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
        // Brief display of tool activity
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
      // On invalid conversation, reset it so next retry starts fresh
      if (err instanceof ApiError && err.status === 400) {
        setConversationId(null);
      }
    } finally {
      setLoading(false);
      setActiveTool([]);
      scrollToBottom(true);
    }
  }, [input, loading, conversationId, scrollToBottom]);

  const handleSuggestion = (text: string) => {
    setInput(text);
    // Use setTimeout so input state updates before send
    setTimeout(() => {
      setInput(text);
    }, 0);
  };

  // When suggestion sets input, auto-send
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [input]);

  return (
    <div className="surface-panel flex h-[600px] flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-5 py-3">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-primary" />
          <h2 className="font-display text-base">CityCare Doctor Assistant</h2>
        </div>
        <button
          id="ai-chat-new"
          onClick={handleNewConversation}
          title="Start new conversation"
          className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-surface hover:text-foreground"
        >
          <RefreshCcw className="h-3.5 w-3.5" />
          New
        </button>
      </div>

      {/* Messages area */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-4 py-4"
      >
        {messages.length === 0 ? (
          <AIEmptyState onSelect={handleSuggestionClick} />
        ) : (
          <div className="space-y-4">
            {messages.map((msg) => (
              <AIMessage key={msg.id} message={msg} />
            ))}
            {loading && activeTool.length > 0 && (
              <AIToolActivity labels={activeTool} />
            )}
            {loading && activeTool.length === 0 && (
              <div className="flex gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary">
                  <Bot className="h-4 w-4" />
                </div>
                <div className="flex items-center gap-1.5 rounded-2xl rounded-tl-sm bg-surface px-4 py-3">
                  <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:0ms]" />
                  <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:150ms]" />
                  <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:300ms]" />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <AIInput
        value={input}
        onChange={setInput}
        onSend={handleSend}
        loading={loading}
      />
    </div>
  );
}
