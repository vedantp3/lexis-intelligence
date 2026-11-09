/**
 * Server-side proxy for POST /api/chat/stream → FastAPI (Server-Sent Events).
 * Authenticates with the NextAuth session, then pipes the backend's event stream through
 * unbuffered so answer text reaches the browser as Gemini generates it.
 */
import { getServerSession } from "next-auth";
import { authOptions } from "../../../../lib/authOptions";
import { API_URL, makeBackendToken } from "../../../../lib/backendToken";

export async function POST(req: Request) {
  const session = await getServerSession(authOptions);
  if (!session?.user?.email) {
    return Response.json({ detail: "Unauthorized. Please sign in." }, { status: 401 });
  }

  const token = await makeBackendToken(session.user.email, session.user.name ?? "Researcher");

  let backendRes: Response;
  try {
    backendRes = await fetch(`${API_URL}/api/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        Authorization: `Bearer ${token}`,
      },
      body: await req.text(),
      signal: req.signal, // stop the backend work if the user navigates away
    });
  } catch {
    return Response.json({ detail: "Could not reach the answer service. Please try again." }, { status: 502 });
  }

  if (!backendRes.ok || !backendRes.body) {
    const raw = await backendRes.text();
    let detail = raw || "Backend returned an empty response.";
    try {
      const parsed = JSON.parse(raw);
      detail = parsed.detail ?? parsed.error ?? detail;
    } catch {
      // keep raw text
    }
    return Response.json({ detail }, { status: backendRes.status || 502 });
  }

  return new Response(backendRes.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
