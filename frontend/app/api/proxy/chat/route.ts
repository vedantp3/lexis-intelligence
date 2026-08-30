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
import { SignJWT } from "jose";
import { authOptions } from "../../../lib/authOptions";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function makeBackendToken(email: string, name: string): Promise<string> {
  const secret = new TextEncoder().encode(process.env.NEXTAUTH_SECRET ?? "dev-secret");
  return new SignJWT({ email, name, user: { email, name } })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("1h")
    .sign(secret);
}

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

  const data = await backendRes.json();
  return Response.json(data, { status: backendRes.status });
}
