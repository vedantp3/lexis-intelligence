"use client";

import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { status } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/login");
    }
  }, [status, router]);

  if (status === "loading") {
    return (
      <div style={loadingStyles.container}>
        <div style={loadingStyles.inner}>
          <div style={loadingStyles.logoMark}>
            <svg width="28" height="28" viewBox="0 0 36 36" fill="none">
              <path d="M18 2L33 10V26L18 34L3 26V10L18 2Z" stroke="#D4AF37" strokeWidth="1.5" fill="none"/>
              <path d="M12 18H24M18 12V24" stroke="#D4AF37" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </div>
          <p style={loadingStyles.text}>Lexis Intelligence</p>
          <div style={loadingStyles.dots}>
            <span style={{ ...loadingStyles.dot, animationDelay: "0ms" }} />
            <span style={{ ...loadingStyles.dot, animationDelay: "150ms" }} />
            <span style={{ ...loadingStyles.dot, animationDelay: "300ms" }} />
          </div>
        </div>
        <style>{`
          @keyframes bounce {
            0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
            40% { transform: scale(1); opacity: 1; }
          }
        `}</style>
      </div>
    );
  }

  if (status === "unauthenticated") {
    return null;
  }

  return <>{children}</>;
}

const loadingStyles: { [key: string]: React.CSSProperties } = {
  container: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "#F8FAFC",
  },
  inner: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "16px",
  },
  logoMark: {
    width: "56px",
    height: "56px",
    borderRadius: "16px",
    background: "rgba(15,23,42,0.05)",
    border: "1px solid rgba(15,23,42,0.08)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  text: {
    fontFamily: "'Hanken Grotesk', sans-serif",
    fontSize: "14px",
    fontWeight: 600,
    color: "#64748B",
    letterSpacing: "0.05em",
  },
  dots: {
    display: "flex",
    gap: "6px",
    marginTop: "4px",
  },
  dot: {
    width: "6px",
    height: "6px",
    borderRadius: "50%",
    background: "#D4AF37",
    animation: "bounce 1.2s infinite",
    display: "inline-block",
  },
};
