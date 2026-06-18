"use client";

import React, { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { streamChat, type Citation } from "../lib/streamChat";

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
}

interface GlobalChatProps {
  apiBaseUrl: string;
}

const SUGGESTED_PROMPTS = [
  "Summarize the latest news from India today.",
  "What are the major international business and economy updates?",
  "Tell me about recent developments in global technology and startups.",
  "Give me a breakdown of recent political and diplomatic discussions.",
];

export default function GlobalChat({ apiBaseUrl }: GlobalChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const latestUserMsgRef = useRef<HTMLDivElement>(null);
  const sessionIdRef = useRef<string>(`global-${Date.now()}`);

  // Scroll to new user message when it is added (keeps view aligned to start of response)
  useEffect(() => {
    if (messages.length > 0) {
      const lastMsg = messages[messages.length - 1];
      if (lastMsg.role === "user" || (lastMsg.role === "assistant" && lastMsg.content === "")) {
        setTimeout(() => {
          latestUserMsgRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 50);
      }
    }
  }, [messages.length]);

  const triggerChat = async (queryText: string) => {
    if (!queryText.trim() || sending) return;

    setSending(true);

    // Add user + empty assistant placeholder
    setMessages((prev) => [
      ...prev,
      { role: "user", content: queryText },
      { role: "assistant", content: "" },
    ]);

    let accumulated = "";

    await streamChat(
      `${apiBaseUrl}/api/chat`,
      queryText,
      sessionIdRef.current,
      {
        onToken: (token) => {
          accumulated += token;
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...updated[updated.length - 1],
              content: accumulated,
            };
            return updated;
          });
        },
        onCitations: (citations) => {
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...updated[updated.length - 1],
              citations,
            };
            return updated;
          });
        },
        onDone: () => setSending(false),
        onError: (error) => {
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...updated[updated.length - 1],
              content: `Error: ${error}`,
            };
            return updated;
          });
          setSending(false);
        },
      }
    );
  };

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    const q = input;
    setInput("");
    triggerChat(q);
  };

  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [input]);

  return (
    <div className="max-w-5xl mx-auto px-4 mt-6 pb-8 flex-1 flex flex-col min-h-0 lg:h-full lg:overflow-hidden w-full">
      {/* Header */}
      <div className="border-b-2 border-[var(--foreground)] pb-2 mb-6 text-center">
        <span className="text-[10px] font-extrabold uppercase tracking-[0.15em] text-[var(--accent)]">
          Global Intelligence Desk
        </span>
        <h2 className="font-serif text-3xl font-black uppercase text-[var(--foreground)] mt-0.5 leading-tight">
          NEWS CHAT
        </h2>
        <p className="text-xs text-[var(--text-secondary)] mt-1.5 max-w-lg mx-auto" style={{ fontFamily: "var(--font-body)" }}>
          Query current global coverage. Responses are grounded in verified publisher dispatches with inline citations.
        </p>
      </div>

      {messages.length === 0 ? (
        /* ─── Empty State ─── */
        <div className="flex-1 flex flex-col items-center justify-center py-6 animate-fade-in-up">
          <div className="w-16 h-16 text-[var(--text-muted)] mb-5 bg-white border border-[var(--border-light)] flex items-center justify-center rounded-full shadow-[var(--shadow-xs)]">
            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <h3 className="font-serif text-xl font-bold mb-1.5 text-[var(--foreground)]">
            Ask The Intelligence Desk
          </h3>
          <p className="text-xs text-[var(--text-secondary)] text-center max-w-sm mb-8 leading-relaxed">
            Search our entire database of current news events. The editorial assistant
            synthesizes a cited report based on matching publications.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-3xl w-full">
            {SUGGESTED_PROMPTS.map((prompt, idx) => (
              <button
                key={idx}
                id={`suggested-prompt-${idx}`}
                onClick={() => triggerChat(prompt)}
                disabled={sending}
                className="text-left bg-white border border-[var(--border-light)] hover:border-[var(--accent)] hover:bg-[var(--background-alt)] p-4 text-[13px] leading-snug rounded-xl text-[var(--text-secondary)] hover:text-[var(--foreground)] transition-all cursor-pointer shadow-[var(--shadow-xs)] hover:shadow-[var(--shadow-sm)] hover:-translate-y-0.5"
                style={{ fontFamily: "var(--font-body)" }}
              >
                <div className="font-semibold text-[var(--text-muted)] mb-1 text-[10px] tracking-wider uppercase">Idea {idx + 1}</div>
                <div>{prompt}</div>
              </button>
            ))}
          </div>
        </div>
      ) : (
        /* ─── Message Area ─── */
        <div className="flex-1 overflow-y-auto pr-2 mb-6 space-y-8 flex flex-col py-4 px-0 md:p-4 w-full">
          {messages.map((msg, idx) => {
            const lastUserMsgIdx = messages.slice().reverse().findIndex(m => m.role === "user");
            const isLatestUser = lastUserMsgIdx !== -1 && idx === (messages.length - 1 - lastUserMsgIdx);
            if (msg.role === "user") {
              return (
                <div
                  key={idx}
                  ref={isLatestUser ? latestUserMsgRef : null}
                  className="flex gap-3 items-start ml-auto justify-end max-w-[85%] md:max-w-[75%] animate-fade-in"
                >
                  <div className="flex flex-col items-end">
                    <span className="text-[9px] font-extrabold text-[var(--text-muted)] uppercase tracking-wider block mb-1">
                      YOU
                    </span>
                    <div
                      className="bg-[var(--foreground)] text-white px-5 py-3 rounded-2xl rounded-tr-sm text-[14px] leading-relaxed shadow-[var(--shadow-xs)]"
                      style={{ fontFamily: "var(--font-body)" }}
                    >
                      {msg.content}
                    </div>
                  </div>
                </div>
              );
            } else {
              if (!msg.content) return null;
              return (
                <div
                  key={idx}
                  className="flex gap-4 items-start w-full animate-fade-in"
                >
                  <div className="w-8 h-8 rounded-full bg-[var(--accent)] text-white flex items-center justify-center font-serif font-black text-xs flex-shrink-0 shadow-[var(--shadow-xs)]">
                    DI
                  </div>
                  <div className="flex-1 space-y-2 min-w-0">
                    <span className="text-[9px] font-extrabold text-[var(--text-muted)] uppercase tracking-wider block">
                      AI DESK
                    </span>
                    <div className="prose-chat text-[15px] leading-relaxed">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg.content || "…"}
                      </ReactMarkdown>
                    </div>

                    {/* Citations */}
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="mt-4 pt-3 border-t border-dashed border-[var(--border)] text-[11px] font-sans">
                        <span className="font-extrabold text-[var(--text-muted)] block uppercase tracking-wider mb-2">
                          Grounded Citations ({msg.citations.length})
                        </span>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-36 overflow-y-auto pr-1">
                          {msg.citations.map((cite, cidx) => (
                            <a
                              key={cidx}
                              href={cite.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-2 bg-white border border-[var(--border-light)] hover:border-[var(--accent)] px-3 py-2 rounded-lg text-[var(--text-secondary)] hover:text-[var(--foreground)] transition-all font-medium hover:underline shadow-[var(--shadow-xs)]"
                            >
                              <span className="bg-[var(--background-alt)] border border-[var(--border-light)] text-[var(--text-muted)] font-extrabold text-[8px] px-1.5 py-0.5 rounded-[2px] uppercase flex-shrink-0">
                                {cite.source_name}
                              </span>
                              <span className="truncate flex-1 text-[11px]">{cite.title}</span>
                              <svg className="w-3 h-3 text-[var(--text-muted)] flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                              </svg>
                            </a>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            }
          })}

          {/* Typing indicator */}
          {sending && messages[messages.length - 1]?.content === "" && (
            <div className="flex gap-4 items-start w-full animate-fade-in">
              <div className="w-8 h-8 rounded-full bg-[var(--accent)] text-white flex items-center justify-center font-serif font-black text-xs flex-shrink-0 shadow-[var(--shadow-xs)]">
                DI
              </div>
              <div className="flex-1 space-y-2">
                <span className="text-[9px] font-extrabold text-[var(--text-muted)] uppercase tracking-wider block">
                  AI DESK
                </span>
                <div className="flex items-center gap-1.5 py-2">
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                </div>
              </div>
            </div>
          )}

        </div>
      )}

      {/* Input Form */}
      <div className="sticky bottom-0 bg-[var(--background)] pt-2 pb-4 z-10 w-full mt-auto">
        <form
          onSubmit={handleSend}
          className="relative flex items-end bg-white border border-[var(--border)] focus-within:border-[var(--accent)] focus-within:ring-2 focus-within:ring-[var(--accent)]/10 p-2 pr-3 pl-4 rounded-3xl shadow-[var(--shadow-md)] transition-all w-full max-w-4xl mx-auto"
        >
          <textarea
            ref={textareaRef}
            id="global-chat-input"
            rows={1}
            placeholder="Ask about recent news (e.g. 'What happened at the G7 summit?')…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend(e);
              }
            }}
            disabled={sending}
            className="flex-1 bg-transparent border-0 text-[14px] text-[var(--foreground)] focus:ring-0 resize-none py-2.5 max-h-44 pr-12 focus:outline-none"
            style={{ fontFamily: "var(--font-body)", lineHeight: "1.5" }}
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            className="absolute right-3 bottom-3 bg-[var(--foreground)] hover:bg-[#3f3a36] disabled:opacity-30 disabled:hover:bg-[var(--foreground)] text-white w-9 h-9 rounded-full flex items-center justify-center transition-all cursor-pointer shadow-[var(--shadow-xs)]"
            title="Query AI Desk"
          >
            <svg className="w-4.5 h-4.5 transform rotate-90" fill="currentColor" viewBox="0 0 24 24">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
            </svg>
          </button>
        </form>
      </div>
    </div>
  );
}

