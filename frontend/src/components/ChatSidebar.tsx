"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import clsx from "clsx";
import { UnauthorizedError } from "@/lib/api";
import { fetchMessages, sendChatMessage, type ChatMessage } from "@/lib/chatApi";

type ChatSidebarProps = {
  onBoardChanged: () => void;
  onSessionExpired?: () => void;
};

type SendState = "idle" | "sending" | "error";

export const ChatSidebar = ({ onBoardChanged, onSessionExpired }: ChatSidebarProps) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [draft, setDraft] = useState("");
  const [sendState, setSendState] = useState<SendState>("idle");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchMessages()
      .then((data) => {
        setMessages(data);
        setHistoryLoaded(true);
      })
      .catch((error) => {
        if (error instanceof UnauthorizedError) {
          onSessionExpired?.();
          return;
        }
        setHistoryLoaded(true);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages, sendState]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = draft.trim();
    if (!trimmed || sendState === "sending") {
      return;
    }

    setSendState("sending");
    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setDraft("");

    try {
      const { reply } = await sendChatMessage(trimmed);
      setMessages((prev) => [...prev, { role: "assistant", content: reply }]);
      setSendState("idle");
      onBoardChanged();
    } catch (error) {
      if (error instanceof UnauthorizedError) {
        onSessionExpired?.();
        return;
      }
      setMessages((prev) => prev.slice(0, -1));
      setDraft(trimmed);
      setSendState("error");
    }
  };

  return (
    <aside className="flex h-[calc(100vh-6rem)] w-full flex-col rounded-[32px] border border-[var(--stroke)] bg-white/80 shadow-[var(--shadow)] backdrop-blur lg:sticky lg:top-12 lg:w-96">
      <div className="border-b border-[var(--stroke)] px-6 py-5">
        <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
          AI Assistant
        </p>
        <h2 className="mt-2 font-display text-xl font-semibold text-[var(--navy-dark)]">
          Ask the board
        </h2>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-6 py-5">
        {!historyLoaded && (
          <p className="text-sm text-[var(--gray-text)]">Loading conversation...</p>
        )}
        {historyLoaded && messages.length === 0 && (
          <p className="text-sm text-[var(--gray-text)]">
            Ask me to create, move, or edit cards on your board.
          </p>
        )}
        {messages.map((message, index) => (
          <div
            key={index}
            className={clsx(
              "max-w-[85%] rounded-2xl px-4 py-2 text-sm leading-5",
              message.role === "user"
                ? "ml-auto bg-[var(--primary-blue)] text-white"
                : "bg-[var(--surface)] text-[var(--navy-dark)]"
            )}
          >
            {message.content}
          </div>
        ))}
        {sendState === "sending" && (
          <div className="max-w-[85%] rounded-2xl bg-[var(--surface)] px-4 py-2 text-sm text-[var(--gray-text)]">
            Thinking...
          </div>
        )}
      </div>

      {sendState === "error" && (
        <div
          role="alert"
          className="mx-6 mb-3 rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-xs text-red-700"
        >
          Couldn&apos;t get a reply. Please try again.
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="flex items-center gap-2 border-t border-[var(--stroke)] px-4 py-4"
      >
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask the assistant..."
          aria-label="Chat message"
          disabled={sendState === "sending"}
          className="flex-1 rounded-full border border-[var(--stroke)] bg-white px-4 py-2 text-sm outline-none transition focus:border-[var(--primary-blue)] disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={sendState === "sending" || !draft.trim()}
          className="rounded-full bg-[var(--secondary-purple)] px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white transition hover:brightness-110 disabled:opacity-60"
        >
          Send
        </button>
      </form>
    </aside>
  );
};
