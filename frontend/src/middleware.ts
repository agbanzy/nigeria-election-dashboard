import { getToken } from "next-auth/jwt";
import { NextRequest, NextResponse } from "next/server";

/**
 * The dashboard is public — results, maps, and analysis need no login.
 * Only the admin surface is gated: /admin (UI) here, and /admin-api/*
 * server-side in its own route handler (which also checks role=admin
 * before injecting X-Admin-Token).
 */
export async function middleware(req: NextRequest) {
  const token = await getToken({
    req,
    secret: process.env.NEXTAUTH_SECRET,
  });

  if (!token) {
    const loginUrl = new URL("/login", req.url);
    loginUrl.searchParams.set("callbackUrl", req.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (token.role !== "admin") {
    return NextResponse.redirect(new URL("/", req.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/admin/:path*"],
};
