"use client";

import React from "react";

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
  size_tier: "lead" | "major" | "standard" | "brief";
  outlet_count: number;
  first_seen_at: string;
  last_updated_at: string;
  articles: Article[];
}

interface NewspaperGridProps {
  clusters: Cluster[];
  onSelectCluster: (clusterId: number) => void;
  loading: boolean;
}

/* ─── Category badge colors ─── */
const CATEGORY_COLORS: Record<string, string> = {
  India: "bg-amber-50 text-amber-800 border-amber-200",
  World: "bg-blue-50 text-blue-800 border-blue-200",
  Tech: "bg-violet-50 text-violet-800 border-violet-200",
  Business: "bg-emerald-50 text-emerald-800 border-emerald-200",
};

function getCategoryClass(cat: string): string {
  return CATEGORY_COLORS[cat] || "bg-[var(--background-alt)] text-[var(--foreground)] border-[var(--border-light)]";
}

function getBentoClasses(index: number, sizeTier: string) {
  // Always make the first one the spotlight lead card
  if (index === 0) {
    return {
      gridClass: "lg:col-span-2 lg:row-span-2 md:col-span-2 bg-white p-7 shadow-[var(--shadow-xs)]",
      titleClass: "text-2xl sm:text-3xl md:text-[2rem] leading-tight font-black font-serif",
      summaryClass: "text-[0.875rem] leading-relaxed",
    };
  }

  // Alternate heights to create bento board depth
  if (sizeTier === "major" || index === 3 || index === 7) {
    return {
      gridClass: "lg:col-span-1 lg:row-span-2 bg-white p-6",
      titleClass: "text-xl md:text-2xl leading-tight font-bold font-serif",
      summaryClass: "text-[0.8rem] leading-relaxed",
    };
  }

  if (sizeTier === "lead" || index === 4) {
    return {
      gridClass: "lg:col-span-2 md:col-span-2 bg-white p-6 shadow-[var(--shadow-xs)]",
      titleClass: "text-xl sm:text-2xl md:text-[1.6rem] leading-tight font-black font-serif",
      summaryClass: "text-[0.85rem] leading-relaxed",
    };
  }

  // Standard cards
  return {
    gridClass: "col-span-1 bg-white p-5 shadow-[var(--shadow-xs)]",
    titleClass: "text-lg md:text-xl leading-tight font-bold font-serif",
    summaryClass: "text-[0.8rem] leading-relaxed",
  };
}

export default function NewspaperGrid({ clusters, onSelectCluster, loading }: NewspaperGridProps) {
  if (true) {
    return (
      <div className="max-w-7xl mx-auto px-6 mt-8 pb-20">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="w-80 space-y-3 p-5 bg-white border border-[var(--border-light)] rounded-[var(--radius)]">
              <div className="skeleton h-4 w-20" />
              <div className="skeleton h-5 w-full" />
              <div className="skeleton h-4 w-full" />
              <div className="skeleton h-4 w-2/3" />
              <div className="skeleton h-3 w-1/3 mt-4" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (clusters.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-20 text-center border-t border-[var(--border-light)] mt-8">
        <h2 className="font-serif text-3xl font-bold mb-3 text-[var(--foreground)]">
          The Printing Press is Quiet
        </h2>
        <p className="text-[var(--text-secondary)] max-w-md mx-auto mb-6 text-sm leading-relaxed">
          No news clusters have been generated for this date yet.
        </p>
      </div>
    );
  }

  const formatTimeAgo = (dateStr: string) => {
    try {
      const diffMs = Date.now() - new Date(dateStr).getTime();
      const diffMins = Math.round(diffMs / 60000);
      const diffHours = Math.round(diffMs / 3600000);
      if (diffMins < 60) return `${diffMins}m ago`;
      if (diffHours < 24) return `${diffHours}h ago`;
      return new Date(dateStr).toLocaleDateString("en-US", { month: "short", day: "numeric" });
    } catch {
      return "recently";
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-6 mt-6 pb-20 animate-fade-in-up">
      {/* Board Title */}
      <div className="border-b-2 border-[var(--foreground)] pb-2 mb-6 flex justify-between items-end">
        <div>
          <span className="text-[10px] font-extrabold uppercase tracking-[0.15em] text-[var(--accent)]">
            Global Dispatch Board
          </span>
          <h2 className="font-serif text-2xl font-black uppercase text-[var(--foreground)] mt-0.5 leading-tight">
            TODAY'S INTEL BOARD
          </h2>
        </div>
        <span className="text-xs text-[var(--text-secondary)] font-extrabold uppercase tracking-wider hidden sm:block">
          {clusters.length} active dispatches &bull; Live coverage
        </span>
      </div>

      {/* Bento Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 auto-rows-auto grid-flow-dense">
        {clusters.map((cluster, index) => {
          const { gridClass, titleClass, summaryClass } = getBentoClasses(index, cluster.size_tier);

          return (
            <div
              key={cluster.id}
              onClick={() => onSelectCluster(cluster.id)}
              className={`
                border border-[var(--foreground)] hover:border-[var(--accent)]
                hover:shadow-[var(--shadow-md)] transition-all duration-200
                rounded-[var(--radius)] flex flex-col justify-between group
                cursor-pointer
                ${gridClass}
              `}
              style={{ animationDelay: `${index * 40}ms` }}
            >
              <div>
                {/* Card Header */}
                <div className="flex items-center justify-between mb-3.5">
                  <span className={`text-[9px] font-extrabold uppercase tracking-wider px-2 py-0.5 rounded-[var(--radius-sm)] border ${getCategoryClass(cluster.category)}`}>
                    {cluster.category}
                  </span>
                  <div className="flex items-center gap-1 text-[9px] font-extrabold text-[var(--accent-warm)] uppercase tracking-wider">
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1M19 20a2 2 0 002-2V8a2 2 0 00-2-2h-5" />
                    </svg>
                    {cluster.outlet_count} sources
                  </div>
                </div>

                {/* Headline */}
                <h4 className={`text-[var(--foreground)] group-hover:text-[var(--accent)] transition-colors duration-200 mb-3 ${titleClass}`}>
                  {cluster.headline}
                </h4>

                {/* Summary */}
                <p className={`text-[var(--text-secondary)] mb-4 text-justify ${summaryClass}`} style={{ fontFamily: "var(--font-body)" }}>
                  {cluster.synthesized_summary}
                </p>
              </div>

              {/* Card Footer */}
              <div className="border-t border-[var(--border-light)] pt-3 flex flex-wrap items-center justify-between gap-2 text-[9px] font-bold uppercase text-[var(--text-muted)]">
                <div className="flex flex-wrap gap-1 items-center max-w-[65%]">
                  <span className="mr-0.5 text-[8px]">SOURCES:</span>
                  {Array.from(new Set(cluster.articles.map((a) => a.source_name))).slice(0, 3).map((source, idx) => (
                    <span key={idx} className="bg-[var(--background-alt)] text-[var(--text-secondary)] px-1.5 py-0.5 rounded-[2px] border border-[var(--border-light)] truncate max-w-[80px]">
                      {source}
                    </span>
                  ))}
                  {Array.from(new Set(cluster.articles.map((a) => a.source_name))).length > 3 && (
                    <span className="text-[8px] text-[var(--text-muted)]">
                      +{(new Set(cluster.articles.map((a) => a.source_name))).size - 3}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[var(--text-muted)]">
                    {formatTimeAgo(cluster.last_updated_at)}
                  </span>
                  <span className="text-[var(--border)]">|</span>
                  <span className="text-[var(--accent)] group-hover:text-[var(--accent-hover)] transition-colors flex items-center gap-0.5 font-extrabold tracking-wider">
                    DISCUSS
                    <svg className="w-2.5 h-2.5 transform group-hover:translate-x-0.5 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M9 5l7 7-7 7" />
                    </svg>
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
