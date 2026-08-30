import type { Metadata } from "next";
import "./globals.css";
import { SessionProviderWrapper } from "./components/SessionProviderWrapper";

export const metadata: Metadata = {
  title: "Lexis Intelligence — Constitution of India AI",
  description:
    "AI-powered constitutional law research platform. Authoritative answers with legal citations, sourced directly from the Constitution of India.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" style={{ height: "100%" }}>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
      </head>
      <body style={{ minHeight: "100%", display: "flex", flexDirection: "column" }}>
        <SessionProviderWrapper>{children}</SessionProviderWrapper>
      </body>
    </html>
  );
}
