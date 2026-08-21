"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "../lib/api";

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.resetPassword(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reset your password. The link may have expired.");
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <main className="authShell">
        <div className="authCard"><h2>Invalid link</h2><p className="lead">This password reset link is missing its token.</p></div>
      </main>
    );
  }

  if (done) {
    return (
      <main className="authShell">
        <div className="authCard">
          <h2>Password updated</h2>
          <p className="lead">You can now sign in with your new password.</p>
          <Link className="primary" href="/" style={{ textAlign: "center", display: "block" }}>Go to sign in</Link>
        </div>
      </main>
    );
  }

  return (
    <main className="authShell">
      <form className="authCard" onSubmit={submit}>
        <h2>Set a new password</h2>
        <label className="field">
          <span>New password</span>
          <input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="At least 8 characters" />
        </label>
        {error && <div className="authError">{error}</div>}
        <button className="primary" type="submit" disabled={loading}>{loading ? "Please wait…" : "Reset password"}</button>
      </form>
    </main>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<main className="authShell"><p style={{ color: "#fff" }}>Loading…</p></main>}>
      <ResetPasswordForm />
    </Suspense>
  );
}
