"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useSession, signOut } from "next-auth/react";
import { AuthGuard } from "./components/AuthGuard";
import { AuditBadge } from "./components/AuditBadge";
import { SourceCard } from "./components/SourceCard";
import type { Message, ChatSession } from "./types";

const STARTER_QUESTIONS = [
  "What are the Fundamental Rights under Part III?",
  "What is the scope and importance of Article 21?",
  "Explain the procedure for impeachment of the President.",
  "What are the grounds for disqualification of Members of Parliament?",
  "How does Article 356 (President's Rule) work?",
];

export default function Home() {
  return (
    <AuthGuard>
      <ChatApp />
    </AuthGuard>
  );
}

function ChatApp() {
  const { data: session } = useSession();
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Welcome to Lexis Intelligence. I am your AI-powered constitutional law assistant, trained on the Constitution of India.\n\nAsk me about any provision, article, fundamental right, directive principle, or constitutional procedure — I will respond with legal citations and a grounding audit.",
    },
  ]);
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeSessionId, setActiveSessionId] = useState<string>(() => crypto.randomUUID());
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Load session history from DB on mount
  useEffect(() => {
    const loadSessions = async () => {
      setSessionsLoading(true);
      try {
        const res = await fetch("/api/proxy/history");
        if (res.ok) {
          const data = await res.json();
          setSessions(
            (data as Array<{ id: string; title: string; first_question?: string; updated_at: string }>).map((s) => ({
              id: s.id,
              title: s.title,
              preview: s.first_question ?? "Constitutional law query",
              timestamp: new Date(s.updated_at),
              messages: [],
            }))
          );
        }
      } catch {
        // Silently ignore — history is a non-critical feature
      } finally {
        setSessionsLoading(false);
      }
    };
    loadSessions();
  }, []);


  const sendMessage = async (event?: FormEvent, overrideQuestion?: string) => {
    event?.preventDefault();
    const trimmed = (overrideQuestion ?? question).trim();
    if (!trimmed || loading) return;

    const userMessage: Message = { role: "user", content: trimmed };
    setMessages((prev) => [...prev, userMessage]);
    setQuestion("");
    setLoading(true);

    if (textareaRef.current) textareaRef.current.style.height = "auto";

    try {
      // Use server-side proxy — auth is handled transparently server-side
      const response = await fetch("/api/proxy/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: trimmed,
          history: [],
          session_id: activeSessionId,
        }),
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Request failed");

      const assistantMessage: Message = {
        role: "assistant",
        content: data.answer.detailed_legal_analysis,
        sources: data.sources,
        audit: data.audit,
        answer: data.answer,
        fromCache: data.from_cache,
        latencyMs: data.latency_ms,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Something went wrong. Please try again.\n\nError: ${error instanceof Error ? error.message : "Unknown error"}`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setQuestion(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
  };

  const newSession = () => {
    const newId = crypto.randomUUID();
    setActiveSessionId(newId);
    setSessions((prev) => [
      {
        id: newId,
        title: "New Research Session",
        preview: "Constitutional law query",
        timestamp: new Date(),
        messages: [],
      },
      ...prev,
    ]);
    setMessages([{
      role: "assistant",
      content: "New research session started. How can I assist you with the Constitution of India?",
    }]);
  };

  const userInitial = session?.user?.name?.[0]?.toUpperCase() ?? "U";
  const userName = session?.user?.name ?? "Researcher";
  const userImage = session?.user?.image;

  return (
    <div style={s.root}>
      {/* CSS Animations */}
      <style>{`
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; } 50% { opacity: 0.4; }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        @keyframes bounce {
          0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
          40% { transform: scale(1); opacity: 1; }
        }
        .msg-bubble { animation: fadeInUp 0.3s ease forwards; }
        .starter-btn:hover {
          border-color: #D4AF37 !important;
          color: #0F172A !important;
          background: rgba(212,175,55,0.06) !important;
          transform: translateY(-1px);
        }
        .send-btn:hover:not(:disabled) {
          background: #1E293B !important;
          box-shadow: 0 4px 14px rgba(15,23,42,0.3) !important;
          transform: translateY(-1px);
        }
        .send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .sidebar-session:hover { background: rgba(15,23,42,0.04) !important; }
        .sidebar-session.active { background: rgba(15,23,42,0.06) !important; border-color: rgba(15,23,42,0.12) !important; }
        .new-chat-btn:hover { background: #1E293B !important; }
        .sign-out-btn:hover { color: #0F172A !important; background: #F1F5F9 !important; }
        .source-toggle:hover { color: #0F172A !important; }
        textarea:focus { outline: none; border-color: #2563EB !important; box-shadow: 0 0 0 3px rgba(37,99,235,0.12) !important; }
      `}</style>

      {/* === SIDEBAR === */}
      {sidebarOpen && (
        <aside style={s.sidebar}>
          <div style={s.sidebarHeader}>
            <div style={s.logoGroup}>
              <div style={s.logoMark}>
                <svg width="18" height="18" viewBox="0 0 36 36" fill="none">
                  <path d="M18 2L33 10V26L18 34L3 26V10L18 2Z" stroke="#D4AF37" strokeWidth="1.8" fill="none"/>
                  <path d="M12 18H24M18 12V24" stroke="#D4AF37" strokeWidth="1.8" strokeLinecap="round"/>
                </svg>
              </div>
              <div>
                <p style={s.logoName}>Lexis Intelligence</p>
                <p style={s.logoSub}>Constitution of India</p>
              </div>
            </div>
          </div>

          <div style={s.sidebarBody}>
            <button className="new-chat-btn" onClick={newSession} style={s.newChatBtn}>
              <span style={{ fontSize: "16px" }}>+</span>
              New Research Session
            </button>

            <p style={s.sectionLabel}>Recent Sessions</p>

            <div style={s.sessionList}>
              {sessionsLoading ? (
                <div style={{ padding: "8px 4px", color: "#94A3B8", fontSize: "12px" }}>Loading history...</div>
              ) : sessions.length === 0 ? (
                <div style={{ padding: "8px 4px", color: "#94A3B8", fontSize: "12px" }}>No sessions yet. Start a query!</div>
              ) : (
                sessions.map((sess) => (
                  <div
                    key={sess.id}
                    className={`sidebar-session${sess.id === activeSessionId ? " active" : ""}`}
                    style={s.sessionItem}
                    onClick={() => {
                      setActiveSessionId(sess.id);
                      setMessages([{ role: "assistant", content: "Session loaded. Continue your research." }]);
                    }}
                  >
                    <div style={s.sessionIcon}>⚖</div>
                    <div style={s.sessionInfo}>
                      <p style={s.sessionTitle}>{sess.title}</p>
                      <p style={s.sessionPreview}>{sess.preview}</p>
                    </div>
                  </div>
                ))
              )}
            </div>


            <div style={s.sidebarDivider} />

            <p style={s.sectionLabel}>Capabilities</p>
            <div style={s.capsList}>
              {[
                { icon: "📖", text: "448 Constitutional Articles" },
                { icon: "🔍", text: "Hybrid RAG Retrieval" },
                { icon: "✓", text: "Grounding Audit" },
                { icon: "✦", text: "Gemini 2.5 Flash" },
              ].map(({ icon, text }) => (
                <div key={text} style={s.capItem}>
                  <span style={s.capIcon}>{icon}</span>
                  <span style={s.capText}>{text}</span>
                </div>
              ))}
            </div>
          </div>

          {/* User panel at bottom of sidebar */}
          <div style={s.userPanel}>
            {userImage ? (
              <img src={userImage} alt={userName} style={s.userAvatar} referrerPolicy="no-referrer" />
            ) : (
              <div style={s.userAvatarFallback}>{userInitial}</div>
            )}
            <div style={s.userInfo}>
              <p style={s.userName}>{userName}</p>
              <p style={s.userRole}>Legal Researcher</p>
            </div>
            <button
              className="sign-out-btn"
              onClick={() => signOut({ callbackUrl: "/login" })}
              style={s.signOutBtn}
              title="Sign out"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>
              </svg>
            </button>
          </div>
        </aside>
      )}

      {/* === MAIN CHAT AREA === */}
      <div style={s.main}>
        {/* Topbar */}
        <header style={s.topbar}>
          <div style={s.topbarLeft}>
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              style={s.menuBtn}
              title="Toggle sidebar"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
              </svg>
            </button>
            {!sidebarOpen && (
              <div style={s.topbarBrand}>
                <div style={s.topbarLogoMark}>
                  <svg width="14" height="14" viewBox="0 0 36 36" fill="none">
                    <path d="M18 2L33 10V26L18 34L3 26V10L18 2Z" stroke="#D4AF37" strokeWidth="2" fill="none"/>
                    <path d="M12 18H24M18 12V24" stroke="#D4AF37" strokeWidth="2" strokeLinecap="round"/>
                  </svg>
                </div>
                <span style={s.topbarBrandName}>Lexis Intelligence</span>
              </div>
            )}
          </div>
          <div style={s.topbarRight}>
            <div style={s.statusDot} />
            <span style={s.statusText}>Backend Connected</span>
          </div>
        </header>

        {/* Messages */}
        <div style={s.messagesArea}>
          <div style={s.messagesInner}>
            {messages.map((msg, index) => (
              <div key={`${msg.role}-${index}`} className="msg-bubble">
                {msg.role === "user" ? (
                  <UserBubble message={msg} userImage={userImage} userInitial={userInitial} />
                ) : (
                  <AssistantBubble message={msg} />
                )}
              </div>
            ))}

            {loading && <ThinkingIndicator />}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input area */}
        <div style={s.inputArea}>
          {/* Starter questions */}
          {messages.length <= 1 && !loading && (
            <div style={s.starterRow}>
              {STARTER_QUESTIONS.map((q) => (
                <button
                  key={q}
                  className="starter-btn"
                  onClick={() => sendMessage(undefined, q)}
                  style={s.starterBtn}
                >
                  {q}
                </button>
              ))}
            </div>
          )}

          <form onSubmit={sendMessage} style={s.inputForm}>
            <div style={s.inputWrapper}>
              <textarea
                ref={textareaRef}
                value={question}
                onChange={handleTextareaChange}
                onKeyDown={handleKeyDown}
                placeholder="Ask about Fundamental Rights, Articles, emergency provisions, amendments..."
                rows={1}
                style={s.textarea}
              />
              <button
                type="submit"
                disabled={loading || !question.trim()}
                className="send-btn"
                style={s.sendBtn}
                title="Send (Enter)"
              >
                {loading ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ animation: "spin 1s linear infinite" }}>
                    <circle cx="12" cy="12" r="10" strokeOpacity="0.3"/>
                    <path d="M12 2a10 10 0 0 1 10 10" strokeLinecap="round"/>
                  </svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <line x1="22" y1="2" x2="11" y2="13"/>
                    <polygon points="22 2 15 22 11 13 2 9 22 2"/>
                  </svg>
                )}
              </button>
            </div>
            <p style={s.hint}>
              Press <kbd style={s.kbd}>Enter</kbd> to send · <kbd style={s.kbd}>Shift+Enter</kbd> for new line
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}

/* ─── Sub-components ─────────────────────────────────────────────────────── */

function UserBubble({
  message,
  userImage,
  userInitial,
}: {
  message: Message;
  userImage?: string | null;
  userInitial: string;
}) {
  return (
    <div style={ub.row}>
      <div style={ub.bubble}>
        <p style={ub.text}>{message.content}</p>
      </div>
      {userImage ? (
        <img src={userImage} alt="You" style={ub.avatar} referrerPolicy="no-referrer" />
      ) : (
        <div style={ub.avatarFallback}>{userInitial}</div>
      )}
    </div>
  );
}

function AssistantBubble({ message }: { message: Message }) {
  const [showSources, setShowSources] = useState(false);
  const hasSources = message.sources && message.sources.length > 0;

  return (
    <div style={ab.row}>
      {/* Avatar */}
      <div style={ab.avatar}>
        <svg width="16" height="16" viewBox="0 0 36 36" fill="none">
          <path d="M18 2L33 10V26L18 34L3 26V10L18 2Z" stroke="#D4AF37" strokeWidth="2" fill="none"/>
          <path d="M12 18H24M18 12V24" stroke="#D4AF37" strokeWidth="2" strokeLinecap="round"/>
        </svg>
      </div>

      <div style={ab.content}>
        {/* Answer summary badge */}
        {message.answer?.summary && (
          <div style={ab.summaryCard}>
            <span style={ab.summaryLabel}>Summary</span>
            <p style={ab.summaryText}>{message.answer.summary}</p>
          </div>
        )}

        {/* Main analysis */}
        <div style={ab.bubble}>
          <p style={ab.text}>{message.content}</p>

          {/* Exceptions */}
          {message.answer?.exceptions_or_limitations && (
            <div style={ab.exceptionsBox}>
              <span style={ab.exceptionsLabel}>Exceptions & Limitations</span>
              <p style={ab.exceptionsText}>{message.answer.exceptions_or_limitations}</p>
            </div>
          )}

          {/* Articles cited chips */}
          {message.answer?.articles_cited && message.answer.articles_cited.length > 0 && (
            <div style={ab.chipRow}>
              {message.answer.articles_cited.map((art) => (
                <span key={art} style={ab.chip}>Art. {art}</span>
              ))}
            </div>
          )}
        </div>

        {/* Meta row */}
        <div style={ab.metaRow}>
          {message.fromCache !== undefined && (
            <span style={message.fromCache ? ab.cacheBadge : ab.liveBadge}>
              {message.fromCache ? "⚡ Cached" : "✦ Live"}
            </span>
          )}
          {message.latencyMs !== undefined && (
            <span style={ab.latency}>{Math.round(message.latencyMs)}ms</span>
          )}
          {hasSources && (
            <button
              className="source-toggle"
              onClick={() => setShowSources(!showSources)}
              style={ab.sourceToggle}
            >
              {showSources ? "▴" : "▾"} {message.sources!.length} source{message.sources!.length !== 1 ? "s" : ""}
            </button>
          )}
        </div>

        {/* Audit badge */}
        {message.audit && <AuditBadge audit={message.audit} />}

        {/* Sources */}
        {showSources && hasSources && (
          <div style={ab.sourcesGrid}>
            {message.sources!.map((src, i) => (
              <SourceCard key={`${src.article}-${i}`} source={src} index={i} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ThinkingIndicator() {
  return (
    <div style={ti.row}>
      <div style={ti.avatar}>
        <svg width="16" height="16" viewBox="0 0 36 36" fill="none">
          <path d="M18 2L33 10V26L18 34L3 26V10L18 2Z" stroke="#D4AF37" strokeWidth="2" fill="none"/>
          <path d="M12 18H24M18 12V24" stroke="#D4AF37" strokeWidth="2" strokeLinecap="round"/>
        </svg>
      </div>
      <div style={ti.bubble}>
        <div style={ti.dots}>
          <span style={{ ...ti.dot, animationDelay: "0ms" }} />
          <span style={{ ...ti.dot, animationDelay: "200ms" }} />
          <span style={{ ...ti.dot, animationDelay: "400ms" }} />
        </div>
        <p style={ti.label}>Consulting the Constitution...</p>
      </div>
      <style>{`
        @keyframes bounce { 0%,80%,100%{transform:scale(0.6);opacity:0.4} 40%{transform:scale(1);opacity:1} }
      `}</style>
    </div>
  );
}

/* ─── Styles ─────────────────────────────────────────────────────────────── */

const s: { [key: string]: React.CSSProperties } = {
  root: {
    display: "flex",
    height: "100vh",
    overflow: "hidden",
    fontFamily: "'Hanken Grotesk', sans-serif",
    background: "#F8FAFC",
  },
  /* SIDEBAR */
  sidebar: {
    width: "280px",
    flexShrink: 0,
    background: "#FFFFFF",
    borderRight: "1px solid #E2E8F0",
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
  },
  sidebarHeader: {
    padding: "20px 20px 16px",
    borderBottom: "1px solid #F1F5F9",
  },
  logoGroup: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
  },
  logoMark: {
    width: "36px",
    height: "36px",
    borderRadius: "10px",
    background: "#0F172A",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  logoName: {
    fontSize: "13px",
    fontWeight: 700,
    color: "#0F172A",
    letterSpacing: "-0.01em",
    lineHeight: 1.2,
  },
  logoSub: {
    fontSize: "10px",
    color: "#94A3B8",
    letterSpacing: "0.05em",
    marginTop: "1px",
  },
  sidebarBody: {
    flex: 1,
    overflowY: "auto" as const,
    padding: "16px",
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },
  newChatBtn: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    width: "100%",
    padding: "10px 14px",
    background: "#0F172A",
    color: "#FFFFFF",
    border: "none",
    borderRadius: "10px",
    cursor: "pointer",
    fontSize: "13px",
    fontWeight: 600,
    fontFamily: "'Hanken Grotesk', sans-serif",
    transition: "background 0.2s",
    letterSpacing: "-0.01em",
  },
  sectionLabel: {
    fontSize: "10px",
    fontWeight: 600,
    letterSpacing: "0.1em",
    textTransform: "uppercase" as const,
    color: "#94A3B8",
    padding: "4px 4px 0",
  },
  sessionList: {
    display: "flex",
    flexDirection: "column",
    gap: "2px",
  },
  sessionItem: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    padding: "10px 12px",
    borderRadius: "8px",
    cursor: "pointer",
    border: "1px solid transparent",
    transition: "all 0.15s",
  },
  sessionIcon: {
    fontSize: "14px",
    width: "24px",
    textAlign: "center" as const,
    flexShrink: 0,
  },
  sessionInfo: {
    overflow: "hidden",
    flex: 1,
  },
  sessionTitle: {
    fontSize: "13px",
    fontWeight: 500,
    color: "#1E293B",
    lineHeight: 1.3,
    whiteSpace: "nowrap" as const,
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  sessionPreview: {
    fontSize: "11px",
    color: "#94A3B8",
    marginTop: "1px",
    whiteSpace: "nowrap" as const,
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  sidebarDivider: {
    height: "1px",
    background: "#F1F5F9",
    margin: "4px 0",
  },
  capsList: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  capItem: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    padding: "0 4px",
  },
  capIcon: {
    fontSize: "13px",
    width: "20px",
    textAlign: "center" as const,
    flexShrink: 0,
  },
  capText: {
    fontSize: "12px",
    color: "#64748B",
  },
  userPanel: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    padding: "14px 16px",
    borderTop: "1px solid #F1F5F9",
    background: "#FAFAFA",
  },
  userAvatar: {
    width: "32px",
    height: "32px",
    borderRadius: "50%",
    flexShrink: 0,
    objectFit: "cover" as const,
  },
  userAvatarFallback: {
    width: "32px",
    height: "32px",
    borderRadius: "50%",
    background: "#0F172A",
    color: "#FFFFFF",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "13px",
    fontWeight: 700,
    flexShrink: 0,
  },
  userInfo: {
    flex: 1,
    overflow: "hidden",
  },
  userName: {
    fontSize: "13px",
    fontWeight: 600,
    color: "#0F172A",
    whiteSpace: "nowrap" as const,
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  userRole: {
    fontSize: "10px",
    color: "#94A3B8",
    marginTop: "1px",
  },
  signOutBtn: {
    background: "transparent",
    border: "none",
    padding: "6px",
    cursor: "pointer",
    color: "#94A3B8",
    borderRadius: "6px",
    display: "flex",
    alignItems: "center",
    transition: "all 0.15s",
    flexShrink: 0,
  },
  /* MAIN */
  main: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
    minWidth: 0,
  },
  topbar: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "14px 24px",
    background: "#FFFFFF",
    borderBottom: "1px solid #E2E8F0",
    flexShrink: 0,
  },
  topbarLeft: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
  },
  menuBtn: {
    background: "transparent",
    border: "none",
    padding: "6px",
    cursor: "pointer",
    color: "#64748B",
    borderRadius: "6px",
    display: "flex",
    alignItems: "center",
    transition: "color 0.15s",
  },
  topbarBrand: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
  topbarLogoMark: {
    width: "28px",
    height: "28px",
    borderRadius: "8px",
    background: "#0F172A",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  topbarBrandName: {
    fontSize: "14px",
    fontWeight: 700,
    color: "#0F172A",
    letterSpacing: "-0.01em",
  },
  topbarRight: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
  },
  statusDot: {
    width: "7px",
    height: "7px",
    borderRadius: "50%",
    background: "#10B981",
    animation: "pulse 2s infinite",
  },
  statusText: {
    fontSize: "12px",
    color: "#64748B",
    fontWeight: 500,
  },
  messagesArea: {
    flex: 1,
    overflowY: "auto" as const,
    padding: "32px 0",
  },
  messagesInner: {
    maxWidth: "820px",
    margin: "0 auto",
    padding: "0 24px",
    display: "flex",
    flexDirection: "column",
    gap: "28px",
  },
  inputArea: {
    background: "#FFFFFF",
    borderTop: "1px solid #E2E8F0",
    padding: "16px 24px 20px",
    flexShrink: 0,
  },
  starterRow: {
    display: "flex",
    flexWrap: "wrap" as const,
    gap: "8px",
    marginBottom: "12px",
    maxWidth: "820px",
    margin: "0 auto 12px",
  },
  starterBtn: {
    padding: "7px 14px",
    background: "#F8FAFC",
    border: "1px solid #E2E8F0",
    borderRadius: "20px",
    cursor: "pointer",
    fontSize: "12px",
    color: "#64748B",
    fontFamily: "'Hanken Grotesk', sans-serif",
    transition: "all 0.2s",
    fontWeight: 500,
  },
  inputForm: {
    maxWidth: "820px",
    margin: "0 auto",
  },
  inputWrapper: {
    display: "flex",
    gap: "10px",
    alignItems: "flex-end",
  },
  textarea: {
    flex: 1,
    padding: "13px 16px",
    background: "#F8FAFC",
    border: "1.5px solid #E2E8F0",
    borderRadius: "12px",
    fontSize: "15px",
    color: "#0F172A",
    fontFamily: "'Hanken Grotesk', sans-serif",
    resize: "none" as const,
    lineHeight: 1.6,
    transition: "border-color 0.2s, box-shadow 0.2s",
    maxHeight: "160px",
    overflowY: "auto" as const,
  },
  sendBtn: {
    width: "46px",
    height: "46px",
    background: "#0F172A",
    border: "none",
    borderRadius: "12px",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "#FFFFFF",
    transition: "all 0.2s",
    flexShrink: 0,
  },
  hint: {
    fontSize: "11px",
    color: "#94A3B8",
    marginTop: "8px",
    textAlign: "center" as const,
  },
  kbd: {
    fontFamily: "monospace",
    fontSize: "10px",
    background: "#F1F5F9",
    border: "1px solid #E2E8F0",
    borderRadius: "4px",
    padding: "0 4px",
    color: "#64748B",
  },
};

// User bubble styles
const ub: { [key: string]: React.CSSProperties } = {
  row: {
    display: "flex",
    justifyContent: "flex-end",
    alignItems: "flex-end",
    gap: "10px",
  },
  bubble: {
    maxWidth: "65%",
    background: "#0F172A",
    borderRadius: "18px 18px 4px 18px",
    padding: "13px 18px",
  },
  text: {
    fontSize: "15px",
    color: "#F8FAFC",
    lineHeight: 1.65,
    whiteSpace: "pre-wrap" as const,
    fontFamily: "'Hanken Grotesk', sans-serif",
  },
  avatar: {
    width: "32px",
    height: "32px",
    borderRadius: "50%",
    flexShrink: 0,
    objectFit: "cover" as const,
  },
  avatarFallback: {
    width: "32px",
    height: "32px",
    borderRadius: "50%",
    background: "linear-gradient(135deg, #D4AF37, #F0D060)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "13px",
    fontWeight: 700,
    color: "#0F172A",
    flexShrink: 0,
  },
};

// Assistant bubble styles
const ab: { [key: string]: React.CSSProperties } = {
  row: {
    display: "flex",
    alignItems: "flex-start",
    gap: "12px",
  },
  avatar: {
    width: "32px",
    height: "32px",
    borderRadius: "50%",
    background: "#0F172A",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
    marginTop: "2px",
    border: "1px solid rgba(212,175,55,0.25)",
  },
  content: {
    flex: 1,
    minWidth: 0,
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },
  summaryCard: {
    background: "rgba(212,175,55,0.06)",
    border: "1px solid rgba(212,175,55,0.2)",
    borderRadius: "10px",
    padding: "10px 14px",
    display: "flex",
    flexDirection: "column",
    gap: "4px",
  },
  summaryLabel: {
    fontSize: "10px",
    fontWeight: 600,
    letterSpacing: "0.1em",
    textTransform: "uppercase" as const,
    color: "#D4AF37",
    fontFamily: "'Hanken Grotesk', sans-serif",
  },
  summaryText: {
    fontSize: "14px",
    color: "#1E293B",
    lineHeight: 1.6,
    fontFamily: "'Source Serif 4', serif",
    fontStyle: "italic",
  },
  bubble: {
    background: "#FFFFFF",
    border: "1px solid #E2E8F0",
    borderRadius: "4px 18px 18px 18px",
    padding: "16px 20px",
    boxShadow: "0 1px 3px rgba(15,23,42,0.05)",
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },
  text: {
    fontSize: "15px",
    color: "#1E293B",
    lineHeight: 1.8,
    whiteSpace: "pre-wrap" as const,
    fontFamily: "'Source Serif 4', serif",
  },
  exceptionsBox: {
    background: "rgba(37,99,235,0.04)",
    border: "1px solid rgba(37,99,235,0.1)",
    borderRadius: "8px",
    padding: "10px 14px",
    display: "flex",
    flexDirection: "column",
    gap: "4px",
  },
  exceptionsLabel: {
    fontSize: "10px",
    fontWeight: 600,
    letterSpacing: "0.1em",
    textTransform: "uppercase" as const,
    color: "#2563EB",
    fontFamily: "'Hanken Grotesk', sans-serif",
  },
  exceptionsText: {
    fontSize: "13px",
    color: "#334155",
    lineHeight: 1.6,
    fontFamily: "'Hanken Grotesk', sans-serif",
  },
  chipRow: {
    display: "flex",
    flexWrap: "wrap" as const,
    gap: "6px",
  },
  chip: {
    fontSize: "11px",
    fontWeight: 600,
    fontFamily: "'Hanken Grotesk', sans-serif",
    color: "#0F172A",
    background: "rgba(15,23,42,0.05)",
    border: "1px solid rgba(15,23,42,0.1)",
    borderRadius: "6px",
    padding: "3px 9px",
    letterSpacing: "0.03em",
  },
  metaRow: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    flexWrap: "wrap" as const,
  },
  cacheBadge: {
    fontSize: "11px",
    fontWeight: 500,
    color: "#D97706",
    background: "#FFFBEB",
    border: "1px solid #FDE68A",
    borderRadius: "6px",
    padding: "2px 8px",
    fontFamily: "'Hanken Grotesk', sans-serif",
  },
  liveBadge: {
    fontSize: "11px",
    fontWeight: 500,
    color: "#059669",
    background: "#ECFDF5",
    border: "1px solid #A7F3D0",
    borderRadius: "6px",
    padding: "2px 8px",
    fontFamily: "'Hanken Grotesk', sans-serif",
  },
  latency: {
    fontSize: "11px",
    color: "#94A3B8",
    fontFamily: "'Hanken Grotesk', sans-serif",
  },
  sourceToggle: {
    fontSize: "12px",
    fontWeight: 500,
    color: "#64748B",
    background: "transparent",
    border: "none",
    cursor: "pointer",
    fontFamily: "'Hanken Grotesk', sans-serif",
    padding: "0",
    transition: "color 0.15s",
    marginLeft: "auto",
  },
  sourcesGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
    gap: "10px",
    marginTop: "4px",
  },
};

// Thinking indicator styles
const ti: { [key: string]: React.CSSProperties } = {
  row: {
    display: "flex",
    alignItems: "flex-start",
    gap: "12px",
  },
  avatar: {
    width: "32px",
    height: "32px",
    borderRadius: "50%",
    background: "#0F172A",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
    border: "1px solid rgba(212,175,55,0.25)",
  },
  bubble: {
    background: "#FFFFFF",
    border: "1px solid #E2E8F0",
    borderRadius: "4px 18px 18px 18px",
    padding: "14px 18px",
    display: "flex",
    alignItems: "center",
    gap: "12px",
  },
  dots: {
    display: "flex",
    gap: "5px",
    alignItems: "center",
  },
  dot: {
    width: "7px",
    height: "7px",
    borderRadius: "50%",
    background: "#D4AF37",
    animation: "bounce 1.2s infinite",
    display: "inline-block",
  },
  label: {
    fontSize: "14px",
    color: "#94A3B8",
    fontStyle: "italic",
    fontFamily: "'Source Serif 4', serif",
  },
};
