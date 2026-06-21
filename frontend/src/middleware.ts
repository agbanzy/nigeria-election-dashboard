import { getToken } from "next-auth/jwt";
import { NextRequest, NextResponse } from "next/server";

const PUBLIC_PATHS = new Set(["/", "/login"]);

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // Allow static assets, NextAuth routes, and public pages. Map geometry
  // (/ng-states.geojson, /maps/*.geojson) is public so the choropleth + the
  // state drill-down maps load without an auth round-trip.
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api/auth") ||
    pathname.startsWith("/maps/") ||
    pathname === "/favicon.ico" ||
    pathname === "/ng-states.geojson" ||
    pathname.endsWith(".geojson") ||
    PUBLIC_PATHS.has(pathname)
  ) {
    return NextResponse.next();
  }

  const token = await getToken({
    req,
    secret: process.env.NEXTAUTH_SECRET,
  });

  if (!token) {
    // API routes return 401; page routes redirect to login
    if (pathname.startsWith("/api/")) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
    const loginUrl = new URL("/login", req.url);
    loginUrl.searchParams.set("callbackUrl", req.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image).*)"],
};
