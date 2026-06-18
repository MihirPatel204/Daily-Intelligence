"use client";

import React, { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Navbar from "../../../components/Navbar";
import { streamChat, type Citation } from "../../../lib/streamChat";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

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

export default function StoryChatPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [cluster, setCluster] = useState<Cluster | null>(null);
  const [loading, setLoading] = useState(true);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  const latestUserMsgRef = useRef<HTMLDivElement>(null);
  const storyTextareaRef = useRef<HTMLTextAreaElement>(null);
  const sessionIdRef = useRef<string>(`story-${id}-${Date.now()}`);

  // Fetch cluster details
  useEffect(() => {
    if (!id) return;

    setLoading(true);
    setMessages([]);
    setCluster(null);
    sessionIdRef.current = `story-${id}-${Date.now()}`;

    fetch(`${API_BASE_URL}/api/clusters/${id}`)
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
  }, [id]);

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

  // Input textarea height adjust
  useEffect(() => {
    if (storyTextareaRef.current) {
      storyTextareaRef.current.style.height = "auto";
      storyTextareaRef.current.style.height = `${Math.min(
        storyTextareaRef.current.scrollHeight,
        140
      )}px`;
    }
  }, [input]);

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
      `${API_BASE_URL}/api/clusters/${id}/chat`,
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
    <div className="flex flex-col min-h-screen lg:h-screen lg:overflow-hidden bg-[var(--background)]">
      {/* Navigation Header */}
      <Navbar
        dateStr={new Date().toLocaleDateString("en-US", {
          weekday: "short",
          month: "short",
          day: "numeric",
        })}
      />

      {loading ? (
        <main className="flex-1 flex flex-col items-center justify-center p-8 gap-3">
          <div className="w-10 h-10 border-[3.5px] border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
          <p className="text-sm italic text-[var(--text-muted)] font-serif">
            Opening Editorial Discuss Room…
          </p>
        </main>
      ) : (
        <main className="flex-1 max-w-7xl mx-auto w-full px-6 py-6 flex flex-col gap-6 min-h-0 lg:overflow-hidden">
          {/* Back Button & Top Summary Header */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between border-b border-[var(--border)] pb-4 gap-4">
            <div className="flex items-center gap-3">
              <button
                onClick={() => router.push("/")}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-[var(--border-light)] hover:border-[var(--accent)] text-xs font-bold uppercase rounded-[var(--radius-sm)] transition-colors cursor-pointer shadow-[var(--shadow-xs)]"
              >
                <svg
                  className="w-3.5 h-3.5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2.5}
                    d="M15 19l-7-7 7-7"
                  />
                </svg>
                Newspaper
              </button>
              <div className="flex items-center gap-2 text-[10px] font-extrabold uppercase text-[var(--text-muted)] tracking-wider">
                <span className="px-2 py-0.5 bg-[var(--background-alt)] rounded-[var(--radius-sm)] border border-[var(--border-light)] text-[var(--foreground)]">
                  {cluster?.category}
                </span>
                <span>&bull;</span>
                <span className="text-[var(--accent)]">
                  {cluster?.outlet_count} Sources
                </span>
              </div>
            </div>
            <h1 className="font-serif font-black text-sm uppercase text-[var(--text-muted)] tracking-[0.1em] text-right hidden sm:block">
              Editorial Chatroom #{id}
            </h1>
          </div>

          {/* Dynamic 2-Column Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 flex-1 min-h-0 items-stretch lg:overflow-hidden">
            {/* Left Column: Context Briefing (1/4 width) */}
            <div className="lg:col-span-1 flex flex-col gap-5 min-h-0 lg:overflow-y-auto pr-1">
              <div className="bg-white border border-[var(--border-light)] p-5 rounded-xl shadow-[var(--shadow-xs)] flex flex-col gap-4">
                <span className="text-[10px] font-extrabold text-[var(--text-muted)] uppercase tracking-wider block border-b border-[var(--border-light)] pb-2">
                  Story Briefing
                </span>
                <h2 className="font-serif font-black text-lg text-[var(--foreground)] leading-tight">
                  {cluster?.headline}
                </h2>
                <p
                  className="text-xs italic text-[var(--text-secondary)] leading-relaxed bg-[var(--background)] p-3 rounded-lg border border-dashed border-[var(--border)]"
                  style={{ fontFamily: "var(--font-body)" }}
                >
                  &ldquo;{cluster?.synthesized_summary}&rdquo;
                </p>
              </div>

              {/* Coverage Links */}
              <div className="bg-white border border-[var(--border-light)] p-5 rounded-xl shadow-[var(--shadow-xs)] flex flex-col gap-3">
                <span className="text-[10px] font-extrabold text-[var(--text-muted)] uppercase tracking-wider block border-b border-[var(--border-light)] pb-2">
                  Contributing Coverage ({cluster?.articles.length})
                </span>
                <div className="flex flex-col gap-2 pr-1">
                  {cluster?.articles.map((art) => (
                    <a
                      key={art.id}
                      href={art.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex flex-col p-2.5 hover:bg-[var(--background-alt)] rounded-lg transition-colors border border-transparent hover:border-[var(--border-light)] leading-snug group"
                      style={{ fontFamily: "var(--font-body)" }}
                    >
                      <span className="font-sans font-bold text-[8px] bg-[var(--background-alt)] border border-[var(--border-light)] text-[var(--text-muted)] px-1 py-0.5 rounded-[2px] uppercase w-fit mb-1.5 transition-colors group-hover:bg-white">
                        {art.source_name}
                      </span>
                      <span className="text-[11.5px] text-[var(--text-secondary)] group-hover:text-[var(--foreground)] underline group-hover:no-underline line-clamp-2">
                        {art.title}
                      </span>
                    </a>
                  ))}
                </div>
              </div>
            </div>

            {/* Right Column: Chat workspace (3/4 width) */}
            <div className="lg:col-span-3 flex flex-col bg-transparent rounded-xl flex-grow h-[70vh] lg:h-full min-h-0 lg:overflow-hidden">
              {/* Messages Thread */}
              <div className="flex-1 overflow-y-auto pr-2 mb-6 space-y-6 flex flex-col p-4 w-full">
                {messages.map((msg, idx) => {
                  const lastUserMsgIdx = messages.slice().reverse().findIndex(m => m.role === "user");
                  const isLatestUser = lastUserMsgIdx !== -1 && idx === (messages.length - 1 - lastUserMsgIdx);
                  if (msg.role === "user") {
                    return (
                      <div
                        key={idx}
                        ref={isLatestUser ? latestUserMsgRef : null}
                        className="flex gap-2 items-start ml-auto justify-end max-w-[85%] md:max-w-[75%] animate-fade-in"
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
                        <div className="w-8 h-8 rounded-full bg-[var(--accent)] text-white flex items-center justify-center font-serif font-black text-[10px] flex-shrink-0 shadow-[var(--shadow-xs)]">
                          ED
                        </div>
                        <div className="flex-1 space-y-2 min-w-0">
                          <span className="text-[9px] font-extrabold text-[var(--text-muted)] uppercase tracking-wider block">
                            EDITORIAL DESK
                          </span>
                          <div className="prose-chat text-[15px] leading-relaxed">
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
                  <div className="flex gap-4 items-start w-full animate-fade-in">
                    <div className="w-8 h-8 rounded-full bg-[var(--accent)] text-white flex items-center justify-center font-serif font-black text-[10px] flex-shrink-0 shadow-[var(--shadow-xs)]">
                      ED
                    </div>
                    <div className="flex-1 space-y-2">
                      <span className="text-[9px] font-extrabold text-[var(--text-muted)] uppercase tracking-wider block">
                        EDITORIAL DESK
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

              {/* Chat Input Capsule */}
              <form
                onSubmit={handleSend}
                className="relative flex items-end bg-white border border-[var(--border)] focus-within:border-[var(--accent)] focus-within:ring-2 focus-within:ring-[var(--accent)]/10 p-2 pr-3 pl-4 rounded-3xl shadow-[var(--shadow-md)] transition-all w-full"
              >
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
                  className="flex-1 bg-transparent border-0 text-[14px] text-[var(--foreground)] focus:ring-0 resize-none py-2.5 max-h-40 pr-12 focus:outline-none"
                  style={{ fontFamily: "var(--font-body)", lineHeight: "1.5", border: "none", outline: "none", boxShadow: "none" }}
                />
                <button
                  type="submit"
                  disabled={sending || !input.trim()}
                  className="absolute right-3 bottom-3 bg-[var(--foreground)] hover:bg-[#3f3a36] disabled:opacity-30 disabled:hover:bg-[var(--foreground)] text-white w-9 h-9 rounded-full flex items-center justify-center transition-all cursor-pointer shadow-[var(--shadow-xs)]"
                >
                  <svg
                    className="w-4.5 h-4.5"
                    fill="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
                  </svg>
                </button>
              </form>
            </div>
          </div>
        </main>
      )}

      {/* Footer */}
      <footer className="w-full bg-[var(--background-alt)] border-t border-[var(--border-light)] py-5 text-center text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.2em] mt-auto">
        &copy; {new Date().getFullYear()} The Daily Intelligence &bull; Powered
        by LangChain &amp; LangGraph RAG
      </footer>
    </div>
  );
}
