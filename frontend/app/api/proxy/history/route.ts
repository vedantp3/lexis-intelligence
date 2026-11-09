/**
 * Server-side proxy for /api/history → FastAPI backend.
 * Supports GET (list sessions) and DELETE (remove session).
 */
import { getServerSession } from "next-auth";
import { authOptions } from "../../../lib/authOptions";
import { API_URL, makeBackendToken } from "../../../lib/backendToken";


export async function GET() {
  const session = await getServerSession(authOptions);
  if (!session?.user?.email) {
    return Response.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const token = await makeBackendToken(session.user.email, session.user.name ?? "Researcher");

  const backendRes = await fetch(`${API_URL}/api/history`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  const data = await backendRes.json();
  return Response.json(data, { status: backendRes.status });
}
