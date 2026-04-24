"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { clearAuth, getEmail, getRole } from "@/lib/auth";

export function Shell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const role = getRole();
  const email = getEmail();

  function logout() {
    clearAuth();
    router.replace("/login");
  }

  return (
    <div className="min-h-screen bg-paper text-ink">
      <header className="border-b border-rule">
        <div className="mx-auto max-w-7xl px-6 py-4 flex items-baseline justify-between">
          <Link href="/dashboard" className="flex items-baseline gap-3">
            <span className="font-display text-2xl font-medium tracking-tight text-navy">
              Fitzrovia
            </span>
            <span className="text-xs uppercase tracking-[0.2em] text-muted">
              Rental Comp
            </span>
          </Link>
          <div className="flex items-center gap-6 text-sm">
            {email && (
              <span className="text-muted">
                {email} · <span className="text-ink">{role}</span>
              </span>
            )}
            <button
              onClick={logout}
              className="text-rust hover:underline underline-offset-4"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-10">{children}</main>
      <footer className="mx-auto max-w-7xl px-6 py-8 text-xs text-muted">
        <div className="hairline mb-4" />
        Asset Management · Competitive Intelligence · Automated Daily
      </footer>
    </div>
  );
}
