"use client";

import React from "react";

interface MastheadProps {
  editionDate: string;
  setEditionDate: (date: string) => void;
  onPrint: () => void;
}

export default function Masthead({ editionDate, setEditionDate, onPrint }: MastheadProps) {
  const formatLongDate = (dateStr: string) => {
    try {
      return new Date(dateStr)
        .toLocaleDateString("en-US", {
          weekday: "long",
          year: "numeric",
          month: "long",
          day: "numeric",
        })
        .toUpperCase();
    } catch {
      return "TODAY";
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-6 mt-8">
      {/* Tagline */}
      <div className="text-center">
        <span className="text-[10px] md:text-[11px] font-bold tracking-[0.3em] text-[var(--accent-warm)] font-serif uppercase">
          AI-Synthesized Global Dispatch
        </span>
      </div>

      {/* Masthead Title */}
      <h1 className="text-center font-serif text-4xl sm:text-6xl md:text-[5.5rem] font-black tracking-tight text-[var(--foreground)] mt-1.5 mb-3 select-none leading-[0.95]">
        THE DAILY INTELLIGENCE
      </h1>

      {/* Issue Details Bar */}
      <div className="border-double-custom py-2.5 flex flex-col md:flex-row items-center justify-between text-[11px] font-semibold tracking-wider text-[var(--text-secondary)] uppercase gap-3">
        <span>PUBLISHED DAILY &bull; WORLDWIDE</span>
        <div className="flex items-center gap-3">
          {/* Edition date picker */}
          <div className="flex items-center gap-1.5 bg-[var(--background-alt)] px-2.5 py-1 rounded-[var(--radius-sm)] border border-[var(--border-light)]">
            <span className="text-[9px] text-[var(--text-muted)] font-bold">EDITION:</span>
            <input
              id="edition-date"
              type="date"
              value={editionDate}
              onChange={(e) => setEditionDate(e.target.value)}
              className="bg-transparent border-none text-[11px] font-bold text-[var(--foreground)] cursor-pointer"
            />
          </div>

          {/* Print button */}
          <button
            id="print-btn"
            onClick={onPrint}
            className="flex items-center gap-1.5 bg-white border border-[var(--border)] hover:border-[var(--foreground)] text-[var(--text-secondary)] hover:text-[var(--foreground)] px-3 py-1 rounded-[var(--radius-sm)] font-bold transition-colors shadow-[var(--shadow-xs)]"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
            </svg>
            Print
          </button>
        </div>
      </div>
    </div>
  );
}
