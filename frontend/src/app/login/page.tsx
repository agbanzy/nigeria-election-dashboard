"use client";

import { signIn } from "next-auth/react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, Suspense } from "react";
import { BRAND_NAME, BRAND_TAGLINE, POWERED_BY_URL, POWERED_BY_TAGLINE } from "@/lib/branding";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const callbackUrl = params.get("callbackUrl") || "/dashboard";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");

    const result = await signIn("credentials", {
      email,
      password,
      redirect: false,
    });

    if (result?.error) {
      setError("Invalid email or password.");
      setLoading(false);
      return;
    }

    router.push(callbackUrl);
  }

  return (
    <div className="min-h-screen bg-[#070d1a] flex flex-col items-center justify-center px-4">
      {/* Background grid */}
      <div
        className="fixed inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(16,185,129,1) 1px, transparent 1px), linear-gradient(90deg, rgba(16,185,129,1) 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
      />

      <div className="relative w-full max-w-sm">
        {/* Logo area */}
        <div className="text-center mb-8">
          <Link href="/" className="inline-block">
            <div className="inline-flex items-center gap-2 mb-3">
              <span className="w-2 h-2 rounded-full bg-[#00a651]" />
              <span className="w-6 h-0.5 bg-[#00a651]" />
              <span className="w-2 h-2 rounded-full bg-[#008751]" />
            </div>
            <h1 className="text-xl font-extrabold text-white tracking-tight">{BRAND_NAME}</h1>
            <p className="text-[11px] text-white/40 mt-1">{BRAND_TAGLINE}</p>
          </Link>
        </div>

        {/* Card */}
        <div className="bg-[#0c1226] border border-[#1f2538] rounded-2xl p-8 shadow-2xl shadow-black/40">
          <h2 className="text-base font-bold text-white mb-1">Sign in</h2>
          <p className="text-[12px] text-white/40 mb-6">Enter your credentials to access the dashboard</p>

          {error && (
            <div className="mb-4 px-4 py-3 rounded-lg bg-red-500/10 border border-red-500/30 text-[13px] text-red-400">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-[12px] font-semibold text-white/60 mb-1.5">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                placeholder="you@example.com"
                className="w-full bg-[#0a0f1e] border border-[#1f2538] rounded-lg px-4 py-2.5 text-[14px] text-white placeholder:text-white/20 focus:outline-none focus:border-[#00a651]/60 focus:ring-1 focus:ring-[#00a651]/30 transition-all"
              />
            </div>

            <div>
              <label className="block text-[12px] font-semibold text-white/60 mb-1.5">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                placeholder="••••••••"
                className="w-full bg-[#0a0f1e] border border-[#1f2538] rounded-lg px-4 py-2.5 text-[14px] text-white placeholder:text-white/20 focus:outline-none focus:border-[#00a651]/60 focus:ring-1 focus:ring-[#00a651]/30 transition-all"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-lg bg-[#00a651] hover:bg-[#008741] disabled:opacity-50 disabled:cursor-not-allowed font-bold text-[14px] text-white transition-all duration-150 mt-2"
            >
              {loading ? "Signing in…" : "Sign in"}
            </button>
          </form>
        </div>

        <p className="text-center text-[11px] text-white/25 mt-6">
          Powered by{" "}
          <a href={POWERED_BY_URL} className="text-white/40 hover:text-white/60 underline transition-colors">
            {POWERED_BY_TAGLINE}
          </a>
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
