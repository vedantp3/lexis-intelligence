"use client";

import { signIn } from "next-auth/react";
import { useState } from "react";

export default function LoginPage() {
  const [loading, setLoading] = useState(false);

  const handleGoogleSignIn = async () => {
    setLoading(true);
    await signIn("google", { callbackUrl: "/" });
  };

  return (
    <main style={styles.main}>
      {/* Background decorative elements */}
      <div style={styles.bgOrb1} />
      <div style={styles.bgOrb2} />
      <div style={styles.bgGrid} />

      <div style={styles.container}>
        {/* Left — Branding panel */}
        <aside style={styles.brandPanel}>
          <div style={styles.brandContent}>
            <div style={styles.logoMark}>
              <svg width="36" height="36" viewBox="0 0 36 36" fill="none">
                <path d="M18 2L33 10V26L18 34L3 26V10L18 2Z" stroke="#D4AF37" strokeWidth="1.5" fill="none"/>
                <path d="M18 8L27 13V23L18 28L9 23V13L18 8Z" fill="#D4AF37" fillOpacity="0.15"/>
                <path d="M12 18H24M18 12V24" stroke="#D4AF37" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </div>
            <div>
              <p style={styles.brandEyebrow}>Lexis Intelligence</p>
              <h1 style={styles.brandTitle}>The Constitution,<br />intelligently decoded.</h1>
            </div>
            <p style={styles.brandSubtitle}>
              AI-powered legal research grounded in the Constitution of India.
              Authoritative answers. Verified citations. Instant clarity.
            </p>

            <div style={styles.featureList}>
              {[
                { icon: "⚖️", label: "Hybrid RAG retrieval across all 448 articles" },
                { icon: "📋", label: "Grounding audit with confidence scoring" },
                { icon: "🔗", label: "Article-level citations with legal context" },
                { icon: "✦", label: "Powered by Gemini 2.5 Flash" },
              ].map(({ icon, label }) => (
                <div key={label} style={styles.featureItem}>
                  <span style={styles.featureIcon}>{icon}</span>
                  <span style={styles.featureLabel}>{label}</span>
                </div>
              ))}
            </div>

            <blockquote style={styles.preambleQuote}>
              <span style={styles.quoteBar} />
              <p>
                &ldquo;We, the people of India, having solemnly resolved to constitute India into a Sovereign
                Socialist Secular Democratic Republic...&rdquo;
              </p>
              <cite style={styles.quoteCite}>— Preamble to the Constitution of India</cite>
            </blockquote>
          </div>
        </aside>

        {/* Right — Sign-in card */}
        <section style={styles.signInPanel}>
          <div style={styles.signInCard}>
            <div style={styles.cardHeader}>
              <div style={styles.cardLogoMini}>
                <svg width="20" height="20" viewBox="0 0 36 36" fill="none">
                  <path d="M18 2L33 10V26L18 34L3 26V10L18 2Z" stroke="#D4AF37" strokeWidth="2" fill="none"/>
                  <path d="M12 18H24M18 12V24" stroke="#D4AF37" strokeWidth="2" strokeLinecap="round"/>
                </svg>
              </div>
              <span style={styles.cardLogoText}>Lexis Intelligence</span>
            </div>

            <div style={styles.cardBody}>
              <h2 style={styles.cardTitle}>Welcome back</h2>
              <p style={styles.cardSubtitle}>
                Sign in to access your constitutional law research workspace.
              </p>

              <button
                onClick={handleGoogleSignIn}
                disabled={loading}
                style={{
                  ...styles.googleButton,
                  ...(loading ? styles.googleButtonLoading : {}),
                }}
                onMouseEnter={(e) => {
                  if (!loading) {
                    (e.currentTarget as HTMLButtonElement).style.backgroundColor = "#F8FAFC";
                    (e.currentTarget as HTMLButtonElement).style.borderColor = "#94A3B8";
                    (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 4px 12px rgba(15,23,42,0.1)";
                  }
                }}
                onMouseLeave={(e) => {
                  if (!loading) {
                    (e.currentTarget as HTMLButtonElement).style.backgroundColor = "#FFFFFF";
                    (e.currentTarget as HTMLButtonElement).style.borderColor = "#E2E8F0";
                    (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 1px 3px rgba(15,23,42,0.06)";
                  }
                }}
              >
                {loading ? (
                  <>
                    <span style={styles.spinner} />
                    Signing in...
                  </>
                ) : (
                  <>
                    <GoogleIcon />
                    Continue with Google
                  </>
                )}
              </button>

              <div style={styles.divider}>
                <span style={styles.dividerLine} />
                <span style={styles.dividerText}>Secure & Private</span>
                <span style={styles.dividerLine} />
              </div>

              <div style={styles.securityBadges}>
                {["🔒 OAuth 2.0", "🛡️ No data stored", "✓ Google-verified"].map((b) => (
                  <span key={b} style={styles.securityBadge}>{b}</span>
                ))}
              </div>
            </div>

            <div style={styles.cardFooter}>
              <p style={styles.footerText}>
                For research and educational purposes only.
                Not legal advice.
              </p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M17.64 9.2045C17.64 8.5663 17.5827 7.9527 17.4764 7.3636H9V10.845H13.8436C13.635 11.97 13.0009 12.9231 12.0477 13.5613V15.8195H14.9564C16.6582 14.2527 17.64 11.9454 17.64 9.2045Z" fill="#4285F4"/>
      <path d="M9 18C11.43 18 13.4673 17.1941 14.9564 15.8195L12.0477 13.5613C11.2418 14.1013 10.2109 14.4204 9 14.4204C6.65591 14.4204 4.67182 12.8372 3.96409 10.71H0.957275V13.0418C2.43818 15.9831 5.48182 18 9 18Z" fill="#34A853"/>
      <path d="M3.96409 10.71C3.78409 10.17 3.68182 9.5931 3.68182 9C3.68182 8.4069 3.78409 7.83 3.96409 7.29V4.9582H0.957275C0.347727 6.1731 0 7.5477 0 9C0 10.4523 0.347727 11.8269 0.957275 13.0418L3.96409 10.71Z" fill="#FBBC05"/>
      <path d="M9 3.5796C10.3214 3.5796 11.5077 4.0336 12.4405 4.9255L15.0218 2.3441C13.4632 0.8918 11.4259 0 9 0C5.48182 0 2.43818 2.0168 0.957275 4.9582L3.96409 7.29C4.67182 5.1627 6.65591 3.5796 9 3.5796Z" fill="#EA4335"/>
    </svg>
  );
}

const styles: { [key: string]: React.CSSProperties } = {
  main: {
    minHeight: "100vh",
    background: "linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F172A 100%)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    position: "relative",
    overflow: "hidden",
    padding: "24px",
  },
  bgOrb1: {
    position: "absolute",
    width: "600px",
    height: "600px",
    borderRadius: "50%",
    background: "radial-gradient(circle, rgba(212,175,55,0.08) 0%, transparent 70%)",
    top: "-200px",
    left: "-100px",
    pointerEvents: "none",
  },
  bgOrb2: {
    position: "absolute",
    width: "500px",
    height: "500px",
    borderRadius: "50%",
    background: "radial-gradient(circle, rgba(37,99,235,0.06) 0%, transparent 70%)",
    bottom: "-150px",
    right: "-100px",
    pointerEvents: "none",
  },
  bgGrid: {
    position: "absolute",
    inset: 0,
    backgroundImage: `
      linear-gradient(rgba(212,175,55,0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(212,175,55,0.03) 1px, transparent 1px)
    `,
    backgroundSize: "64px 64px",
    pointerEvents: "none",
  },
  container: {
    display: "flex",
    maxWidth: "1100px",
    width: "100%",
    minHeight: "640px",
    borderRadius: "24px",
    overflow: "hidden",
    boxShadow: "0 32px 80px rgba(0,0,0,0.5)",
    position: "relative",
    zIndex: 1,
    flexWrap: "wrap",
  },
  brandPanel: {
    flex: "1 1 420px",
    background: "linear-gradient(160deg, #0F172A 0%, #111827 100%)",
    borderRight: "1px solid rgba(212,175,55,0.15)",
    padding: "64px 48px",
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
  },
  brandContent: {
    display: "flex",
    flexDirection: "column",
    gap: "32px",
  },
  logoMark: {
    width: "56px",
    height: "56px",
    borderRadius: "16px",
    background: "rgba(212,175,55,0.1)",
    border: "1px solid rgba(212,175,55,0.25)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  brandEyebrow: {
    fontFamily: "'Hanken Grotesk', sans-serif",
    fontSize: "11px",
    fontWeight: 600,
    letterSpacing: "0.18em",
    textTransform: "uppercase" as const,
    color: "#D4AF37",
    marginBottom: "12px",
  },
  brandTitle: {
    fontFamily: "'Source Serif 4', serif",
    fontSize: "38px",
    fontWeight: 700,
    lineHeight: 1.2,
    color: "#F8FAFC",
    letterSpacing: "-0.02em",
  },
  brandSubtitle: {
    fontFamily: "'Hanken Grotesk', sans-serif",
    fontSize: "15px",
    lineHeight: 1.7,
    color: "#94A3B8",
  },
  featureList: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },
  featureItem: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
  },
  featureIcon: {
    fontSize: "16px",
    width: "24px",
    textAlign: "center" as const,
  },
  featureLabel: {
    fontFamily: "'Hanken Grotesk', sans-serif",
    fontSize: "14px",
    color: "#CBD5E1",
    lineHeight: 1.5,
  },
  preambleQuote: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
    padding: "20px 20px 20px 24px",
    background: "rgba(212,175,55,0.05)",
    borderRadius: "12px",
    border: "1px solid rgba(212,175,55,0.12)",
    position: "relative",
  },
  quoteBar: {
    position: "absolute",
    left: 0,
    top: 0,
    bottom: 0,
    width: "3px",
    borderRadius: "3px 0 0 3px",
    background: "linear-gradient(180deg, #D4AF37, rgba(212,175,55,0.3))",
  },
  quoteCite: {
    fontFamily: "'Hanken Grotesk', sans-serif",
    fontSize: "11px",
    letterSpacing: "0.1em",
    color: "#D4AF37",
    fontStyle: "normal",
    textTransform: "uppercase" as const,
  },
  signInPanel: {
    flex: "1 1 380px",
    background: "#FFFFFF",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "48px",
  },
  signInCard: {
    width: "100%",
    maxWidth: "360px",
  },
  cardHeader: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    marginBottom: "40px",
  },
  cardLogoMini: {
    width: "36px",
    height: "36px",
    borderRadius: "10px",
    background: "rgba(212,175,55,0.08)",
    border: "1px solid rgba(212,175,55,0.2)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  cardLogoText: {
    fontFamily: "'Hanken Grotesk', sans-serif",
    fontSize: "15px",
    fontWeight: 600,
    color: "#0F172A",
    letterSpacing: "-0.01em",
  },
  cardBody: {
    display: "flex",
    flexDirection: "column",
    gap: "20px",
  },
  cardTitle: {
    fontFamily: "'Source Serif 4', serif",
    fontSize: "28px",
    fontWeight: 700,
    color: "#0F172A",
    letterSpacing: "-0.02em",
    lineHeight: 1.2,
  },
  cardSubtitle: {
    fontFamily: "'Hanken Grotesk', sans-serif",
    fontSize: "15px",
    color: "#64748B",
    lineHeight: 1.6,
    marginTop: "-8px",
  },
  googleButton: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "10px",
    width: "100%",
    padding: "13px 20px",
    backgroundColor: "#FFFFFF",
    border: "1px solid #E2E8F0",
    borderRadius: "10px",
    cursor: "pointer",
    fontFamily: "'Hanken Grotesk', sans-serif",
    fontSize: "15px",
    fontWeight: 500,
    color: "#0F172A",
    transition: "all 0.2s ease",
    boxShadow: "0 1px 3px rgba(15,23,42,0.06)",
    letterSpacing: "-0.01em",
  },
  googleButtonLoading: {
    opacity: 0.7,
    cursor: "not-allowed",
  },
  spinner: {
    width: "16px",
    height: "16px",
    border: "2px solid #E2E8F0",
    borderTop: "2px solid #0F172A",
    borderRadius: "50%",
    display: "inline-block",
    animation: "spin 0.8s linear infinite",
  },
  divider: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    margin: "4px 0",
  },
  dividerLine: {
    flex: 1,
    height: "1px",
    background: "#E2E8F0",
  },
  dividerText: {
    fontFamily: "'Hanken Grotesk', sans-serif",
    fontSize: "11px",
    color: "#94A3B8",
    letterSpacing: "0.08em",
    textTransform: "uppercase" as const,
    whiteSpace: "nowrap" as const,
  },
  securityBadges: {
    display: "flex",
    gap: "8px",
    flexWrap: "wrap" as const,
  },
  securityBadge: {
    fontFamily: "'Hanken Grotesk', sans-serif",
    fontSize: "11px",
    color: "#475569",
    background: "#F8FAFC",
    border: "1px solid #E2E8F0",
    borderRadius: "6px",
    padding: "4px 10px",
  },
  cardFooter: {
    marginTop: "32px",
    paddingTop: "20px",
    borderTop: "1px solid #F1F5F9",
  },
  footerText: {
    fontFamily: "'Hanken Grotesk', sans-serif",
    fontSize: "12px",
    color: "#94A3B8",
    lineHeight: 1.6,
    textAlign: "center" as const,
  },
};
