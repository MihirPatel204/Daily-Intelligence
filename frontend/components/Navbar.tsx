"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

interface NavbarProps {
  dateStr: string;
}

export default function Navbar({ dateStr }: NavbarProps) {
  const pathname = usePathname();
  const activeTab = pathname.startsWith("/chat") ? "search" : "edition";

  return (
    <header className="w-full bg-white/80 backdrop-blur-sm border-b border-[var(--border-light)] sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-6 py-3 flex flex-col md:flex-row items-center justify-between gap-3">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-[var(--foreground)] text-white flex items-center justify-center rounded-[var(--radius-sm)] shadow-[var(--shadow-xs)]">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
          </div>
          <div>
            <span className="font-serif font-extrabold text-lg tracking-tight text-[var(--foreground)]">
              NewsRAG
            </span>
            <p className="text-[9px] uppercase tracking-[0.2em] text-[var(--text-muted)] font-semibold leading-tight">
              AI Editorial Intelligence
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav id="main-nav" className="flex items-center gap-0.5 bg-[var(--background-alt)] p-1 rounded-[var(--radius)] border border-[var(--border-light)]">
          <Link
            id="tab-edition"
            href="/"
            className={`px-5 py-1.5 text-[11px] font-bold uppercase tracking-wider transition-all duration-200 rounded-[var(--radius-sm)] ${
              activeTab === "edition"
                ? "bg-[var(--foreground)] text-white shadow-[var(--shadow-xs)]"
                : "text-[var(--text-secondary)] hover:text-[var(--foreground)] hover:bg-white/60"
            }`}
          >
            Daily Edition
          </Link>
          <Link
            id="tab-search"
            href="/chat"
            className={`px-5 py-1.5 text-[11px] font-bold uppercase tracking-wider flex items-center gap-1.5 transition-all duration-200 rounded-[var(--radius-sm)] ${
              activeTab === "search"
                ? "bg-[var(--foreground)] text-white shadow-[var(--shadow-xs)]"
                : "text-[var(--text-secondary)] hover:text-[var(--foreground)] hover:bg-white/60"
            }`}
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            News Chat
          </Link>
        </nav>

      </div>
    </header>
  );
}
