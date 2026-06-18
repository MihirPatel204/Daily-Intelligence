"use client";

import React from "react";
import Navbar from "../../components/Navbar";
import GlobalChat from "../../components/GlobalChat";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export default function ChatPage() {
  return (
    <div className="flex flex-col min-h-screen lg:h-screen lg:overflow-hidden bg-[var(--background)]">
      <Navbar
        dateStr={new Date().toLocaleDateString("en-US", {
          weekday: "short",
          month: "short",
          day: "numeric",
        })}
      />
      <main className="flex-1 flex flex-col min-h-0 lg:overflow-hidden">
        <GlobalChat apiBaseUrl={API_BASE_URL} />
      </main>
      <footer className="w-full bg-[var(--background-alt)] border-t border-[var(--border-light)] py-5 text-center text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.2em] mt-auto">
        &copy; {new Date().getFullYear()} The Daily Intelligence &bull; Powered
        by LangChain &amp; LangGraph RAG
      </footer>
    </div>
  );
}
