import { GroundingValidation } from "../types";

interface AuditBadgeProps {
  audit: GroundingValidation;
}

export function AuditBadge({ audit }: AuditBadgeProps) {
  const pct = Math.round(audit.confidence_score * 100);
  const verified = audit.is_faithful;

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div style={styles.statusRow}>
          <span style={verified ? styles.dotGreen : styles.dotRed} />
          <span style={styles.label}>Grounding Audit</span>
        </div>
        <span style={verified ? styles.badgeGreen : styles.badgeRed}>
          {verified ? "Verified" : "Flagged"}
        </span>
      </div>

      {/* Confidence bar */}
      <div style={styles.barWrapper}>
        <div style={styles.barTrack}>
          <div
            style={{
              ...styles.barFill,
              width: `${pct}%`,
              background: pct >= 80
                ? "linear-gradient(90deg, #10B981, #34D399)"
                : pct >= 60
                ? "linear-gradient(90deg, #F59E0B, #FBBF24)"
                : "linear-gradient(90deg, #F43F5E, #FB7185)",
            }}
          />
        </div>
        <span style={styles.pctLabel}>{pct}%</span>
      </div>
      <p style={styles.confLabel}>Confidence Score</p>

      {audit.unsupported_claims.length > 0 && (
        <div style={styles.claimsBox}>
          <p style={styles.claimsTitle}>Unsupported Claims</p>
          <ul style={styles.claimsList}>
            {audit.unsupported_claims.map((claim, i) => (
              <li key={i} style={styles.claimItem}>
                <span style={styles.claimBullet}>↳</span>
                {claim}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    marginTop: "14px",
    padding: "12px 14px",
    background: "rgba(248,250,252,0.8)",
    border: "1px solid #E2E8F0",
    borderRadius: "10px",
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
  },
  statusRow: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
  },
  dotGreen: {
    width: "6px",
    height: "6px",
    borderRadius: "50%",
    background: "#10B981",
    display: "inline-block",
  },
  dotRed: {
    width: "6px",
    height: "6px",
    borderRadius: "50%",
    background: "#F43F5E",
    display: "inline-block",
  },
  label: {
    fontFamily: "'Hanken Grotesk', sans-serif",
    fontSize: "11px",
    fontWeight: 600,
    letterSpacing: "0.08em",
    textTransform: "uppercase" as const,
    color: "#64748B",
  },
  badgeGreen: {
    fontFamily: "'Hanken Grotesk', sans-serif",
    fontSize: "11px",
    fontWeight: 600,
    color: "#059669",
    background: "#ECFDF5",
    border: "1px solid #A7F3D0",
    borderRadius: "6px",
    padding: "2px 8px",
  },
  badgeRed: {
    fontFamily: "'Hanken Grotesk', sans-serif",
    fontSize: "11px",
    fontWeight: 600,
    color: "#E11D48",
    background: "#FFF1F2",
    border: "1px solid #FECDD3",
    borderRadius: "6px",
    padding: "2px 8px",
  },
  barWrapper: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
  },
  barTrack: {
    flex: 1,
    height: "5px",
    background: "#E2E8F0",
    borderRadius: "99px",
    overflow: "hidden",
  },
  barFill: {
    height: "100%",
    borderRadius: "99px",
    transition: "width 0.6s ease",
  },
  pctLabel: {
    fontFamily: "'Hanken Grotesk', sans-serif",
    fontSize: "12px",
    fontWeight: 600,
    color: "#334155",
    minWidth: "30px",
    textAlign: "right" as const,
  },
  confLabel: {
    fontFamily: "'Hanken Grotesk', sans-serif",
    fontSize: "11px",
    color: "#94A3B8",
    marginTop: "-4px",
  },
  claimsBox: {
    marginTop: "4px",
    padding: "10px 12px",
    background: "#FFF1F2",
    border: "1px solid #FECDD3",
    borderRadius: "8px",
  },
  claimsTitle: {
    fontFamily: "'Hanken Grotesk', sans-serif",
    fontSize: "11px",
    fontWeight: 600,
    color: "#E11D48",
    letterSpacing: "0.06em",
    textTransform: "uppercase" as const,
    marginBottom: "6px",
  },
  claimsList: {
    listStyle: "none",
    display: "flex",
    flexDirection: "column",
    gap: "4px",
  },
  claimItem: {
    fontFamily: "'Hanken Grotesk', sans-serif",
    fontSize: "12px",
    color: "#9F1239",
    lineHeight: 1.5,
    display: "flex",
    gap: "6px",
  },
  claimBullet: {
    color: "#E11D48",
    flexShrink: 0,
  },
};
