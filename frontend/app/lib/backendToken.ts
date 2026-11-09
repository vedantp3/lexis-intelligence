/**
 * Shared helpers for the server-side proxy routes: backend URL and the short-lived HS256 JWT
 * the FastAPI backend verifies (signed with NEXTAUTH_SECRET).
 */
import { SignJWT } from "jose";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

export async function makeBackendToken(email: string, name: string): Promise<string> {
  const secret = new TextEncoder().encode(process.env.NEXTAUTH_SECRET ?? "dev-secret");
  return new SignJWT({ email, name, user: { email, name } })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("1h")
    .sign(secret);
}
