"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { Role } from "./types";

const TOKEN_KEY = "fitz_token";
const ROLE_KEY  = "fitz_role";
const EMAIL_KEY = "fitz_email";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function getRole(): Role | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ROLE_KEY) as Role | null;
}

export function getEmail(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(EMAIL_KEY);
}

export function setAuth(token: string, role: Role, email: string) {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(ROLE_KEY, role);
  window.localStorage.setItem(EMAIL_KEY, email);
}

export function clearAuth() {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(ROLE_KEY);
  window.localStorage.removeItem(EMAIL_KEY);
}

/** Redirect to /login if not authenticated. Returns null while checking. */
export function useAuthGuard(): { ready: boolean; role: Role | null; email: string | null } {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [role, setRole] = useState<Role | null>(null);
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    setRole(getRole());
    setEmail(getEmail());
    setReady(true);
  }, [router]);

  return { ready, role, email };
}
