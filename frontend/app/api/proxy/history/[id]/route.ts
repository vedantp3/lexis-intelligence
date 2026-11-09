/**
 * Server-side proxy for GET /api/history/{session_id} → FastAPI backend.
 * Returns one saved session and its messages (the backend checks that the user owns it).
 */
import { getServerSession } from "next-auth";
import { authOptions } from "../../../../lib/authOptions";
import { API_URL, makeBackendToken } from "../../../../lib/backendToken";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const session = await getServerSession(authOptions);
  if (!session?.user?.email) {
    return Response.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const token = await makeBackendToken(session.user.email, session.user.name ?? "Researcher");

  const backendRes = await fetch(`${API_URL}/api/history/${encodeURIComponent(id)}`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  const raw = await backendRes.text();
  try {
    return Response.json(JSON.parse(raw), { status: backendRes.status });
  } catch {
    return Response.json({ detail: "Backend returned an invalid response." }, { status: 502 });
  }
}
