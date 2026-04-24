"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { getToken, setAuth } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // If already signed in, skip straight to dashboard.
  useEffect(() => {
    if (getToken()) router.replace("/dashboard");
  }, [router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const resp = await api.login(email, password);
      setAuth(resp.access_token, resp.role, resp.email);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen grid md:grid-cols-5 bg-paper text-ink">
      {/* Editorial side panel */}
      <div className="hidden md:flex md:col-span-2 bg-navy text-paper flex-col justify-between p-12">
        <div>
          <div className="font-display text-3xl font-medium tracking-tight">
            Fitzrovia
          </div>
          <div className="text-[0.7rem] uppercase tracking-[0.2em] text-paper/70 mt-1">
            Rental Comp
          </div>
        </div>
        <div>
          <div className="font-display text-display-lg leading-tight">
            Competitive intelligence,{" "}
            <span className="italic text-rust">automated.</span>
          </div>
          <div className="hairline my-6 border-paper/20" />
          <div className="text-sm text-paper/70 leading-relaxed max-w-sm">
            Daily pricing and incentive data across eleven midtown Toronto
            buildings. Same rooms, same week, same source of truth.
          </div>
        </div>
        <div className="text-xs text-paper/50 tracking-wide">
          Asset Management · Internal tool
        </div>
      </div>

      {/* Form */}
      <div className="md:col-span-3 flex items-center justify-center p-8">
        <form onSubmit={submit} className="w-full max-w-sm">
          <div className="font-display text-display-lg text-navy mb-1">
            Sign in
          </div>
          <div className="text-sm text-muted mb-8">
            Use your Fitzrovia credentials to continue.
          </div>

          <label className="block text-[0.7rem] uppercase tracking-[0.18em] text-muted mb-1.5">
            Email
          </label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full mb-5 px-3 py-2.5 bg-transparent border border-rule focus:border-navy outline-none transition-colors"
            autoComplete="email"
          />

          <label className="block text-[0.7rem] uppercase tracking-[0.18em] text-muted mb-1.5">
            Password
          </label>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full mb-6 px-3 py-2.5 bg-transparent border border-rule focus:border-navy outline-none transition-colors"
            autoComplete="current-password"
          />

          {error && (
            <div className="mb-4 px-3 py-2 bg-rust/10 border-l-2 border-rust text-sm text-ink">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full px-4 py-3 bg-navy text-paper hover:bg-ink transition-colors font-medium tracking-wide"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
