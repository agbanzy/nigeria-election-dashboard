/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // In production on DO App Platform, the static site and the Flask `web`
    // service sit behind the same router and `/api/*` is mapped to `web`
    // directly via `.do/app.yaml`. The rewrite below is only used in local
    // dev where Next.js needs to proxy to the backend.
    const target =
      process.env.API_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://127.0.0.1:8080";
    return [
      {
        source: "/api/:path*",
        destination: `${target}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
