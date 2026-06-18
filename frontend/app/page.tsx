"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Navbar from "../components/Navbar";
import Masthead from "../components/Masthead";
import NewspaperGrid from "../components/NewspaperGrid";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export default function Home() {
  const router = useRouter();
  const [editionDate, setEditionDate] = useState(() => {
    return new Date().toISOString().split("T")[0];
  });

  const [clusters, setClusters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [ingesting, setIngesting] = useState(false);
  const [ingestStatus, setIngestStatus] = useState<string | null>(null);

  const fetchClusters = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/clusters`);
      if (!res.ok) throw new Error("Failed to fetch stories");
      const data = await res.json();
      setClusters(data);
    } catch (err) {
      console.error("Error fetching clusters:", err);
      setClusters([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClusters();

    // Auto-refresh the edition content from the backend every 30 seconds
    const interval = setInterval(() => {
      // Avoid loading state overlay flash during auto-refresh
      fetch(`${API_BASE_URL}/api/clusters`)
        .then((res) => {
          if (res.ok) return res.json();
          throw new Error("Polling failed");
        })
        .then((data) => setClusters(data))
        .catch((err) => console.error("Error polling clusters:", err));
    }, 30000);

    return () => clearInterval(interval);
  }, [editionDate]);

  const handleIngest = async () => {
    setIngesting(true);
    setIngestStatus("Initializing the ingestion engine…");
    try {
      const res = await fetch(`${API_BASE_URL}/api/ingest`, { method: "POST" });
      if (!res.ok) throw new Error("Ingestion trigger failed");
      setIngestStatus(
        "Pipeline started — feeds are being fetched and clustered. Refreshing in 15 seconds…"
      );
      setTimeout(() => {
        fetchClusters();
        setIngestStatus(null);
        setIngesting(false);
      }, 15000);
    } catch (err) {
      console.error(err);
      setIngestStatus("Failed to start ingestion. Check backend connectivity.");
      setIngesting(false);
    }
  };

  const handlePrint = () => window.print();

  return (
    <div className="flex flex-col min-h-screen">
      {/* Top Navigation */}
      <Navbar
        dateStr={new Date(editionDate).toLocaleDateString("en-US", {
          weekday: "short",
          month: "short",
          day: "numeric",
        })}
      />

      <main className="flex-1 flex flex-col">
        {/* Newspaper Masthead */}
        <Masthead
          editionDate={editionDate}
          setEditionDate={setEditionDate}
          onPrint={handlePrint}
        />

        {/* Empty-state welcome banner */}
        {!loading && clusters.length === 0 && (
          <div className="max-w-3xl mx-auto w-full px-6 mt-10 animate-fade-in-up">
            <div className="bg-white border border-[var(--border)] p-8 text-center shadow-[var(--shadow-sm)] rounded-[var(--radius)]">
              <div className="w-14 h-14 mx-auto mb-4 bg-[var(--background-alt)] border border-[var(--border-light)] rounded-full flex items-center justify-center">
                <svg className="w-7 h-7 text-[var(--accent)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1M19 20a2 2 0 002-2V8a2 2 0 00-2-2h-5M19 20l-7-7" />
                </svg>
              </div>
              <h3 className="font-serif font-bold text-xl mb-2 text-[var(--foreground)]">
                Welcome to the Editorial Office
              </h3>
              <p className="text-sm text-[var(--text-secondary)] max-w-md mx-auto mb-5 leading-relaxed">
                The database is empty. Click below to poll live RSS feeds,
                run the clustering engine, and generate AI-synthesized stories.
              </p>
              <button
                id="ingest-trigger"
                onClick={handleIngest}
                disabled={ingesting}
                className="bg-[var(--foreground)] hover:bg-[#3f3a36] disabled:opacity-50 text-white text-xs font-bold uppercase tracking-wider px-6 py-2.5 rounded-[var(--radius-sm)] transition-all cursor-pointer"
              >
                {ingesting ? "Running Ingestion…" : "Initialize & Ingest News Feeds"}
              </button>
              {ingestStatus && (
                <p className="text-xs font-semibold text-[var(--accent)] mt-4 animate-pulse">
                  {ingestStatus}
                </p>
              )}
            </div>
          </div>
        )}

        {/* Background refresh banner */}
        {ingesting && clusters.length > 0 && (
          <div className="max-w-7xl mx-auto w-full px-6 mt-4">
            <div className="bg-[#eef6fb] border border-[#c4dce8] text-[#31708f] px-4 py-2.5 text-xs font-semibold text-center rounded-[var(--radius-sm)]">
              Refreshing feeds in the background. Fresh dispatches will appear shortly…
            </div>
          </div>
        )}

        {/* Story Grid */}
        <NewspaperGrid
          clusters={clusters}
          onSelectCluster={(id) => router.push(`/chat/${id}`)}
          loading={loading}
        />
      </main>

      {/* Footer */}
      <footer className="w-full bg-[var(--background-alt)] border-t border-[var(--border-light)] py-5 text-center text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.2em] mt-auto">
        &copy; {new Date().getFullYear()} The Daily Intelligence &bull; Powered
        by LangChain &amp; LangGraph RAG
      </footer>
    </div>
  );
}
