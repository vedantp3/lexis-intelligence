/**
 * Client for the streaming chat endpoint (/api/proxy/chat/stream → FastAPI SSE).
 *
 * The backend streams the answer as plain text in four labelled sections:
 *   ### SUMMARY / ### ANALYSIS / ### EXCEPTIONS / ### ARTICLES
 * and finishes with a `final` event carrying the parsed answer + grounding audit.
 */
import type { ConstitutionalAnswer, GroundingValidation, SourceChunk } from "../types";

export type FinalPayload = {
  answer: ConstitutionalAnswer;
  audit: GroundingValidation;
  sources: SourceChunk[];
  model: string;
  provider: string;
  latency_ms: number;
  from_cache: boolean;
  session_id?: string;
};

export type StreamSections = {
  summary: string;
  analysis: string;
  exceptions: string;
  articles: string[];
  /** Section currently being written (null before the first heading arrives). */
  current: "SUMMARY" | "ANALYSIS" | "EXCEPTIONS" | "ARTICLES" | null;
};

type Handlers = {
  onSources?: (sources: SourceChunk[]) => void;
  onText?: (sections: StreamSections, rawText: string) => void;
};

const HEADING = /^\s*#{2,4}\s*(SUMMARY|ANALYSIS|EXCEPTIONS|ARTICLES)\s*:?\s*$/gim;

/** Parse (possibly incomplete) streamed text into sections. */
export function parseSections(raw: string): StreamSections {
  // Hide a heading that is still arriving ("### ANAL") at the very end of the buffer.
  const text = raw.replace(/\n\s*#[^\n]*$/, "\n");
  const out: StreamSections = { summary: "", analysis: "", exceptions: "", articles: [], current: null };
  const matches = [...text.matchAll(HEADING)];
  if (matches.length === 0) {
    out.analysis = text.trim().startsWith("#") ? "" : text.trim();
    return out;
  }
  matches.forEach((m, i) => {
    const start = (m.index ?? 0) + m[0].length;
    const end = i + 1 < matches.length ? matches[i + 1].index ?? text.length : text.length;
    const body = text.slice(start, end).trim();
    const name = m[1].toUpperCase() as NonNullable<StreamSections["current"]>;
    if (name === "SUMMARY") out.summary = body;
    else if (name === "ANALYSIS") out.analysis = body;
    else if (name === "EXCEPTIONS") out.exceptions = body;
    else
      out.articles = body
        .split(/[,;\n]/)
        .map((a) => a.replace(/^(Article|Art\.)\s*/i, "").trim())
        .filter(Boolean);
    out.current = name;
  });
  return out;
}

/** POST a question and consume the SSE stream. Resolves with the final payload. */
export async function streamChat(
  body: { question: string; session_id: string; history?: unknown[] },
  handlers: Handlers = {},
  signal?: AbortSignal
): Promise<FinalPayload> {
  const res = await fetch("/api/proxy/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ history: [], ...body }),
    signal,
  });

  if (!res.ok || !res.body) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      detail = data.detail || data.error || detail;
    } catch {
      // non-JSON error body
    }
    throw new Error(detail);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let text = "";
  let final: FinalPayload | null = null;

  const handleEvent = (block: string) => {
    let event = "message";
    const dataLines: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
    }
    if (dataLines.length === 0) return;
    const data = JSON.parse(dataLines.join("\n"));
    if (event === "sources") handlers.onSources?.(data.sources);
    else if (event === "delta") {
      text += data.text;
      handlers.onText?.(parseSections(text), text);
    } else if (event === "final") final = data as FinalPayload;
    else if (event === "error") throw new Error(data.detail || "Chat processing failed.");
  };

  for (;;) {
    const { value, done } = await reader.read();
    if (value) buffer += decoder.decode(value, { stream: true });
    buffer = buffer.replace(/\r\n/g, "\n");
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      if (block.trim()) handleEvent(block);
    }
    if (done) break;
  }
  if (buffer.trim()) handleEvent(buffer);

  if (!final) throw new Error("The answer stream ended unexpectedly. Please try again.");
  return final;
}
