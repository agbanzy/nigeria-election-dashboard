/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // In production on DO App Platform, the static site and the Flask `web`
    // service sit behind the same router: `/api/*` is mapped to `web` and
    // `/api/auth/*` to this Next.js app (NextAuth) via `.do/app.yaml` ingress.
    // The rewrite below is only used in local dev where Next.js proxies to the
    // backend.
    //
    // CRITICAL: exclude `/api/auth/*` from the proxy so NextAuth's own route
    // handler (app/api/auth/[...nextauth]) serves session/csrf/callback/etc.
    // Without the exclusion the rewrite forwards those to Flask, which 404s
    // (or refuses the connection), breaking login.
    const target =
      process.env.API_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://127.0.0.1:8080";
    return [
      {
        source: "/api/:path((?!auth(?:/|$)).*)",
        destination: `${target}/api/:path`,
      },
    ];
  },
};

export default nextConfig;
