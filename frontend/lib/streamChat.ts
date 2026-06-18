/**
 * SSE Streaming Chat Helper
 *
 * Connects to a FastAPI StreamingResponse endpoint that sends
 * Server-Sent Events with JSON payloads:
 *   - { type: "token",     content: "..." }
 *   - { type: "citations", citations: [...] }
 *   - { type: "error",     content: "..." }
 *   - [DONE]
 */

export interface Citation {
  title: string;
  url: string;
  source_name: string;
}

export interface StreamCallbacks {
  onToken: (token: string) => void;
  onCitations: (citations: Citation[]) => void;
  onDone: () => void;
  onError: (error: string) => void;
}

export async function streamChat(
  url: string,
  message: string,
  sessionId: string,
  callbacks: StreamCallbacks
): Promise<void> {
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: sessionId }),
    });

    if (!response.ok) {
      callbacks.onError(`Request failed (HTTP ${response.status})`);
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      callbacks.onError("No response body available");
      return;
    }

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE frames are separated by double newlines
      const frames = buffer.split("\n\n");
      buffer = frames.pop() || "";

      for (const frame of frames) {
        const match = frame.match(/^data:\s*(.+)$/m);
        if (!match) continue;
        const data = match[1].trim();

        if (data === "[DONE]") {
          callbacks.onDone();
          return;
        }

        try {
          const parsed = JSON.parse(data);
          switch (parsed.type) {
            case "token":
              if (parsed.content) callbacks.onToken(parsed.content);
              break;
            case "citations":
              callbacks.onCitations(parsed.citations || []);
              break;
            case "error":
              callbacks.onError(parsed.content || "Unknown server error");
              break;
          }
        } catch {
          // Partial JSON — will be completed in next chunk
        }
      }
    }

    callbacks.onDone();
  } catch (error) {
    callbacks.onError(
      error instanceof Error ? error.message : "Network error"
    );
  }
}
