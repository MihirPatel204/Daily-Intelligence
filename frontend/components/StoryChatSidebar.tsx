"use client";

import React, { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { streamChat, type Citation } from "../lib/streamChat";

interface Article {
  id: number;
  source_name: string;
  title: string;
  url: string;
  published_at: string;
}

interface Cluster {
  id: number;
  headline: string;
  synthesized_summary: string;
  category: string;
  score: number;
  size_tier: string;
  outlet_count: number;
  first_seen_at: string;
  last_updated_at: string;
  articles: Article[];
}

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
}

interface StoryChatSidebarProps {
  clusterId: number | null;
  onClose: () => void;
  apiBaseUrl: string;
}

export default function StoryChatSidebar({
  clusterId,
  onClose,
  apiBaseUrl,
}: StoryChatSidebarProps) {
  const [cluster, setCluster] = useState<Cluster | null>(null);
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const latestUserMsgRef = useRef<HTMLDivElement>(null);
  const sessionIdRef = useRef<string>(`story-${clusterId}-${Date.now()}`);

  // Fetch cluster details
  useEffect(() => {
    if (!clusterId) return;

    setLoading(true);
    setMessages([]);
    setCluster(null);
    sessionIdRef.current = `story-${clusterId}-${Date.now()}`;

    fetch(`${apiBaseUrl}/api/clusters/${clusterId}`)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to fetch cluster");
        return res.json();
      })
      .then((data) => {
        setCluster(data);
        const outlets = Array.from(
          new Set(data.articles.map((a: Article) => a.source_name))
        ).join(", ");
        setMessages([
          {
            role: "assistant",
            content: `Welcome to the Editorial Desk. I have compiled **${data.outlet_count} reports** regarding this event from outlets including ${outlets}. Ask me anything about this story!`,
          },
        ]);
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [clusterId, apiBaseUrl]);

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

  const storyTextareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (storyTextareaRef.current) {
      storyTextareaRef.current.style.height = "auto";
      storyTextareaRef.current.style.height = `${Math.min(storyTextareaRef.current.scrollHeight, 120)}px`;
    }
  }, [input]);

  if (!clusterId) return null;

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || sending) return;

    const userMsg = input.trim();
    setInput("");
    setSending(true);

    // Add user message + empty assistant placeholder
    setMessages((prev) => [
      ...prev,
      { role: "user", content: userMsg },
      { role: "assistant", content: "" },
    ]);

    let accumulated = "";

    await streamChat(
      `${apiBaseUrl}/api/clusters/${clusterId}/chat`,
      userMsg,
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

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/30 backdrop-blur-[2px] animate-fade-in"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="relative w-full md:max-w-2xl bg-[var(--background)] h-full shadow-[var(--shadow-lg)] flex flex-col md:border-l border-[var(--border)] z-10 animate-slide-in-right">

        {/* Header */}
        <div className="p-4 border-b border-[var(--border-light)] flex items-center justify-between bg-white">
          <div className="flex items-center gap-2 text-[11px] font-bold uppercase text-[var(--text-muted)]">
            <span className="px-2 py-0.5 bg-[var(--background-alt)] rounded-[var(--radius-sm)] text-[var(--foreground)] border border-[var(--border-light)]">
              {cluster?.category || "…"}
            </span>
            <span>&bull;</span>
            <span className="text-[var(--accent)]">
              {cluster?.outlet_count || 0} Outlets
            </span>
          </div>
          <button
            id="close-sidebar"
            onClick={onClose}
            className="p-1.5 rounded-full hover:bg-[var(--background-alt)] text-[var(--text-secondary)] hover:text-[var(--foreground)] transition-colors"
          >
            <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {loading ? (
          <div className="flex-1 flex flex-col items-center justify-center p-8 gap-3">
            <div className="w-8 h-8 border-[3px] border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
            <p className="text-sm italic text-[var(--text-muted)]" style={{ fontFamily: "var(--font-body)" }}>
              Fetching editorial briefing…
            </p>
          </div>
        ) : (
          <div className="flex-1 overflow-hidden flex flex-col">

            {/* Story Context */}
            <div className="p-5 bg-white border-b border-[var(--border-light)] overflow-y-auto max-h-[28%] shadow-[var(--shadow-xs)]">
              <h3 className="font-serif font-black text-lg text-[var(--foreground)] leading-tight mb-2">
                {cluster?.headline}
              </h3>
              <p className="text-xs italic text-[var(--text-secondary)] leading-relaxed bg-[var(--background)] p-3 rounded-[var(--radius-sm)] border border-dashed border-[var(--border)]" style={{ fontFamily: "var(--font-body)" }}>
                &ldquo;{cluster?.synthesized_summary}&rdquo;
              </p>
            </div>

            {/* Chat Messages */}
            <div className="flex-1 overflow-y-auto p-5 space-y-6">
              {messages.map((msg, idx) => {
                const lastUserMsgIdx = messages.slice().reverse().findIndex(m => m.role === "user");
                const isLatestUser = lastUserMsgIdx !== -1 && idx === (messages.length - 1 - lastUserMsgIdx);
                if (msg.role === "user") {
                  return (
                    <div
                      key={idx}
                      ref={isLatestUser ? latestUserMsgRef : null}
                      className="flex gap-2 items-start ml-auto justify-end max-w-[85%] animate-fade-in"
                    >
                      <div className="flex flex-col items-end">
                        <span className="text-[9px] font-extrabold text-[var(--text-muted)] uppercase tracking-wider block mb-1">
                          YOU
                        </span>
                        <div
                          className="bg-[var(--foreground)] text-white px-4 py-2.5 rounded-2xl rounded-tr-sm text-[13px] leading-relaxed shadow-[var(--shadow-xs)]"
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
                      className="flex gap-3 items-start w-full animate-fade-in"
                    >
                      <div className="w-7 h-7 rounded-full bg-[var(--accent)] text-white flex items-center justify-center font-serif font-black text-[10px] flex-shrink-0 shadow-[var(--shadow-xs)]">
                        ED
                      </div>
                      <div className="flex-1 space-y-1.5 min-w-0">
                        <span className="text-[9px] font-extrabold text-[var(--text-muted)] uppercase tracking-wider block">
                          EDITORIAL DESK
                        </span>
                        <div className="prose-chat text-[13.5px] leading-relaxed">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {msg.content || "…"}
                          </ReactMarkdown>
                        </div>
                      </div>
                    </div>
                  );
                }
              })}

              {/* Typing indicator */}
              {sending && messages[messages.length - 1]?.content === "" && (
                <div className="flex gap-3 items-start w-full animate-fade-in">
                  <div className="w-7 h-7 rounded-full bg-[var(--accent)] text-white flex items-center justify-center font-serif font-black text-[10px] flex-shrink-0 shadow-[var(--shadow-xs)]">
                    ED
                  </div>
                  <div className="flex-1 space-y-1.5">
                    <span className="text-[9px] font-extrabold text-[var(--text-muted)] uppercase tracking-wider block">
                      EDITORIAL DESK
                    </span>
                    <div className="flex items-center gap-1.5 py-1.5">
                      <span className="typing-dot" />
                      <span className="typing-dot" />
                      <span className="typing-dot" />
                    </div>
                  </div>
                </div>
              )}

            </div>

            {/* Source Coverage */}
            <div className="p-4 bg-[var(--background-alt)] border-t border-b border-[var(--border-light)] text-xs shadow-[var(--shadow-xs)]">
              <span className="font-extrabold text-[10px] tracking-wider text-[var(--text-muted)] block mb-2 uppercase">
                Contributing Feeds ({cluster?.articles.length})
              </span>
              <div className="flex flex-col gap-1.5 max-h-20 overflow-y-auto pr-2">
                {cluster?.articles.map((art) => (
                  <a
                    key={art.id}
                    href={art.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-start gap-1.5 text-[var(--text-secondary)] hover:text-[var(--accent)] transition-colors leading-tight"
                    style={{ fontFamily: "var(--font-body)" }}
                  >
                    <span className="font-sans font-bold text-[9px] bg-white border border-[var(--border)] text-[var(--text-muted)] px-1 rounded-[2px] uppercase flex-shrink-0">
                      {art.source_name}
                    </span>
                    <span className="underline hover:no-underline line-clamp-1 text-[11px]">
                      {art.title}
                    </span>
                  </a>
                ))}
              </div>
            </div>

            {/* Chat Input */}
            <form
              onSubmit={handleSend}
              className="p-4 bg-white border-t border-[var(--border-light)] flex items-end gap-2"
            >
              <div className="relative flex-1 flex items-end bg-[var(--background)] border border-[var(--border)] focus-within:border-[var(--accent)] focus-within:ring-2 focus-within:ring-[var(--accent)]/10 p-1.5 pr-2.5 pl-3 rounded-2xl transition-all">
                <textarea
                  ref={storyTextareaRef}
                  id="story-chat-input"
                  rows={1}
                  placeholder="Ask about this story…"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSend(e);
                    }
                  }}
                  disabled={sending}
                  className="flex-1 bg-transparent border-0 text-sm text-[var(--foreground)] focus:ring-0 resize-none py-1.5 max-h-32 pr-10 focus:outline-none"
                  style={{ fontFamily: "var(--font-body)", lineHeight: "1.4" }}
                />
                <button
                  type="submit"
                  disabled={sending || !input.trim()}
                  className="absolute right-2 bottom-2 bg-[var(--foreground)] hover:bg-[#3f3a36] disabled:opacity-30 disabled:hover:bg-[var(--foreground)] text-white w-7 h-7 rounded-full flex items-center justify-center transition-all cursor-pointer shadow-[var(--shadow-xs)]"
                >
                  <svg className="w-3.5 h-3.5 transform rotate-90" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
                  </svg>
                </button>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}

