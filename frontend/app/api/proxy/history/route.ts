/**
 * Server-side proxy for /api/history → FastAPI backend.
 * Supports GET (list sessions) and DELETE (remove session).
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
