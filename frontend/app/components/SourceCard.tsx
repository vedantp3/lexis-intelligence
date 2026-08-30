import { SourceChunk } from "../types";

interface SourceCardProps {
  source: SourceChunk;
  index: number;
}

export function SourceCard({ source, index }: SourceCardProps) {
  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <span style={styles.chip}>Art. {source.article}</span>
        <span style={styles.part}>{source.part}</span>
      </div>
      <p style={styles.title}>{source.title}</p>
      <p style={styles.snippet}>&ldquo;{source.snippet}&rdquo;</p>
    </div>
  );
}

const styles: { [key: string]: React.CSSProperties } = {
  card: {
    background: "rgba(15,23,42,0.03)",
    border: "1px solid #E2E8F0",
    borderRadius: "10px",
    padding: "12px 14px",
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
  chip: {
    fontFamily: "'Hanken Grotesk', sans-serif",
    fontSize: "11px",
    fontWeight: 600,
    letterSpacing: "0.06em",
    color: "#0F172A",
    background: "rgba(15,23,42,0.06)",
    border: "1px solid rgba(15,23,42,0.12)",
    borderRadius: "6px",
    padding: "2px 8px",
  },
  part: {
    fontFamily: "'Hanken Grotesk', sans-serif",
    fontSize: "11px",
    color: "#94A3B8",
    letterSpacing: "0.04em",
  },
  title: {
    fontFamily: "'Hanken Grotesk', sans-serif",
    fontSize: "13px",
    fontWeight: 600,
    color: "#1E293B",
    lineHeight: 1.4,
  },
  snippet: {
    fontFamily: "'Source Serif 4', serif",
    fontSize: "12px",
    color: "#64748B",
    lineHeight: 1.6,
    fontStyle: "italic",
    borderLeft: "2px solid #D4AF37",
    paddingLeft: "10px",
    marginTop: "2px",
  },
};
