"use client";

import type { CSSProperties } from "react";
import type { VoiceState } from "../lib/useVoiceConversation";

const LABELS: Record<VoiceState, { title: string; hint: string; color: string }> = {
  idle: { title: "Voice mode off", hint: "", color: "#94A3B8" },
  listening: { title: "Listening…", hint: "Ask your question. I'll answer when you pause.", color: "#2563EB" },
  processing: { title: "Consulting the Constitution…", hint: "Searching provisions and drafting a grounded answer.", color: "#D4AF37" },
  speaking: { title: "Speaking…", hint: "Start talking or press Esc to interrupt.", color: "#059669" },
};

type Props = {
  state: VoiceState;
  interim: string;
  error: string | null;
  onInterrupt: () => void;
  onStop: () => void;
};

export function VoiceBar({ state, interim, error, onInterrupt, onStop }: Props) {
  const label = LABELS[state];

  if (error && state === "idle") {
    return (
      <div style={{ ...v.bar, borderColor: "#FCA5A5", background: "#FEF2F2" }} role="alert">
        <span style={{ ...v.title, color: "#B91C1C" }}>Voice mode unavailable</span>
        <span style={v.hint}>{error}</span>
      </div>
    );
  }

  return (
    <div style={v.bar} aria-live="polite">
      <style>{`
        @keyframes voice-ring { 0% { transform: scale(1); opacity: 0.55; } 100% { transform: scale(1.9); opacity: 0; } }
        @keyframes voice-wave { 0%, 100% { transform: scaleY(0.35); } 50% { transform: scaleY(1); } }
        @keyframes voice-spin { to { transform: rotate(360deg); } }
        .voice-btn:hover { background: #F1F5F9 !important; color: #0F172A !important; }
      `}</style>

      <div style={v.orbWrap}>
        {state === "listening" && <span style={{ ...v.ring, borderColor: label.color }} />}
        <div style={{ ...v.orb, background: label.color }}>
          {state === "listening" && (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round">
              <rect x="9" y="2" width="6" height="12" rx="3" />
              <path d="M5 10v1a7 7 0 0 0 14 0v-1M12 18v4" />
            </svg>
          )}
          {state === "processing" && <span style={v.spinner} />}
          {state === "speaking" && (
            <div style={v.wave}>
              {[0, 1, 2, 3].map((i) => (
                <span key={i} style={{ ...v.waveBar, animationDelay: `${i * 120}ms` }} />
              ))}
            </div>
          )}
        </div>
      </div>

      <div style={v.text}>
        <span style={{ ...v.title, color: label.color }}>{label.title}</span>
        <span style={v.hint}>{interim ? `“${interim}”` : label.hint}</span>
      </div>

      <div style={v.actions}>
        {state === "speaking" && (
          <button type="button" className="voice-btn" onClick={onInterrupt} style={v.btn}>
            Interrupt
          </button>
        )}
        <button type="button" className="voice-btn" onClick={onStop} style={v.btn}>
          End voice
        </button>
      </div>
    </div>
  );
}

const v: Record<string, CSSProperties> = {
  bar: {
    maxWidth: "820px",
    margin: "0 auto 12px",
    display: "flex",
    alignItems: "center",
    gap: "14px",
    padding: "10px 14px",
    background: "#F8FAFC",
    border: "1px solid #E2E8F0",
    borderRadius: "14px",
  },
  orbWrap: { position: "relative", width: "38px", height: "38px", flexShrink: 0 },
  ring: {
    position: "absolute",
    inset: 0,
    borderRadius: "50%",
    border: "2px solid",
    animation: "voice-ring 1.4s ease-out infinite",
  },
  orb: {
    position: "absolute",
    inset: 0,
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    transition: "background 0.3s",
  },
  spinner: {
    width: "16px",
    height: "16px",
    borderRadius: "50%",
    border: "2.5px solid rgba(255,255,255,0.35)",
    borderTopColor: "#fff",
    animation: "voice-spin 0.8s linear infinite",
  },
  wave: { display: "flex", alignItems: "center", gap: "2px", height: "16px" },
  waveBar: {
    width: "3px",
    height: "16px",
    borderRadius: "2px",
    background: "#fff",
    animation: "voice-wave 0.9s ease-in-out infinite",
  },
  text: { flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: "2px" },
  title: { fontSize: "13px", fontWeight: 700, letterSpacing: "-0.01em" },
  hint: {
    fontSize: "12px",
    color: "#64748B",
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  actions: { display: "flex", gap: "6px", flexShrink: 0 },
  btn: {
    padding: "6px 12px",
    fontSize: "12px",
    fontWeight: 600,
    color: "#475569",
    background: "#FFFFFF",
    border: "1px solid #E2E8F0",
    borderRadius: "8px",
    cursor: "pointer",
    fontFamily: "inherit",
  },
};
