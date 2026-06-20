import { getServerSession } from "next-auth";
import { NextRequest, NextResponse } from "next/server";
import { authOptions } from "@/lib/auth";

/**
 * Server-side admin proxy. Lives at /admin-api/* (NOT /api/*, so DO ingress
 * routes it to this Next.js app rather than Flask). It verifies the caller is
 * an authenticated admin via the NextAuth session, then forwards the request to
 * Flask's /api/admin/* with the X-Admin-Token header. The token (ADMIN_TOKEN)
 * stays server-side and is never exposed to the browser.
 */

const API_URL =
  process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8080";
const ADMIN_TOKEN = process.env.ADMIN_TOKEN || "";

async function requireAdmin() {
  const session = await getServerSession(authOptions);
  const role = (session?.user as { role?: string } | undefined)?.role;
  return Boolean(session && role === "admin");
}

function targetUrl(req: NextRequest, path: string[]) {
  const search = req.nextUrl.search || "";
  return `${API_URL}/api/admin/${path.join("/")}${search}`;
}

export async function GET(req: NextRequest, ctx: { params: { path: string[] } }) {
  if (!(await requireAdmin())) {
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }
  const res = await fetch(targetUrl(req, ctx.params.path), {
    headers: { "X-Admin-Token": ADMIN_TOKEN },
    cache: "no-store",
  });
  const body = await res.text();
  return new NextResponse(body, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
  });
}

export async function POST(req: NextRequest, ctx: { params: { path: string[] } }) {
  if (!(await requireAdmin())) {
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }
  const payload = await req.text();
  const res = await fetch(targetUrl(req, ctx.params.path), {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Admin-Token": ADMIN_TOKEN },
    body: payload,
    cache: "no-store",
  });
  const body = await res.text();
  return new NextResponse(body, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
  });
}
