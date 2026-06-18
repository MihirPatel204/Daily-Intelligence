"use client";

import React, { useRef } from "react";
import ChatInterface from "./ChatInterface";

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
  const sessionIdRef = useRef<string>(`global-${Date.now()}`);

  return (
    <div className="max-w-5xl mx-auto px-4 mt-6 pb-8 flex-1 flex flex-col min-h-0 lg:h-full lg:overflow-hidden w-full">
      <ChatInterface
        apiUrl={`${apiBaseUrl}/api/chat`}
        sessionId={sessionIdRef.current}
        placeholder="Ask about recent news…"
        suggestedPrompts={SUGGESTED_PROMPTS}
        avatarLabel="DI"
        roleLabel="AI DESK"
      />
    </div>
  );
}
