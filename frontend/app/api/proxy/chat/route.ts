/**
 * Server-side proxy for POST /api/chat → FastAPI backend.
 *
 * Why a proxy?
 * NextAuth JWT cookies are HTTP-only — JavaScript can't read them.
 * This server route uses getServerSession() (runs on the server) to get
 * the authenticated user, creates a signed HS256 JWT the backend can verify,
 * then forwards the request to FastAPI.
 */
import { getServerSession } from "next-auth";
import { authOptions } from "../../../lib/authOptions";
import { API_URL, makeBackendToken } from "../../../lib/backendToken";


export async function POST(req: Request) {
  const session = await getServerSession(authOptions);

  if (!session?.user?.email) {
    return Response.json({ detail: "Unauthorized. Please sign in." }, { status: 401 });
  }

  const token = await makeBackendToken(
    session.user.email,
    session.user.name ?? "Researcher"
  );

  const body = await req.json();

  const backendRes = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });

  const raw = await backendRes.text();
  const data = raw ? JSON.parse(raw) : { detail: "Backend returned an empty response." };
  return Response.json(data, { status: backendRes.status });
}
