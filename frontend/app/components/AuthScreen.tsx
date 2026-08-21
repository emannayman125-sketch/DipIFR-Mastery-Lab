"use client";

import { useState } from "react";
import { api, ApiError } from "../lib/api";

type Mode = "login" | "register" | "forgot";

export default function AuthScreen({ onAuthenticated }: { onAuthenticated: (displayName: string) => void }) {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const reset = () => {
    setError(null);
    setNotice(null);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    reset();
    setLoading(true);
    try {
      if (mode === "forgot") {
        const res = await api.forgotPassword(email);
        setNotice(res.detail);
      } else {
        mode === "login"
          ? await api.login(email, password)
          : await api.register(email, password, displayName || "Student");
        onAuthenticated(mode === "register" ? displayName || "Student" : email.split("@")[0]);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="authShell">
      <form className="authCard" onSubmit={submit}>
        <div className="brand"><div className="brandMark">D</div><div><strong>DipIFR</strong><span>Mastery Lab</span></div></div>
        <h2>{mode === "login" ? "Welcome back" : mode === "register" ? "Create your account" : "Reset your password"}</h2>
        <p className="lead">
          {mode === "login" && "Sign in to resume your saved progress."}
          {mode === "register" && "Your progress is private and tied to your account."}
          {mode === "forgot" && "Enter your email and we'll send you a reset link."}
        </p>

        {mode === "register" && (
          <label className="field">
            <span>Display name</span>
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="e.g. Sara" />
          </label>
        )}
        <label className="field">
          <span>Email</span>
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
        </label>

        {mode !== "forgot" && (
          <label className="field">
            <span>Password</span>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
            />
          </label>
        )}

        {error && <div className="authError">{error}</div>}
        {notice && <div className="success">{notice}</div>}

        <button className="primary" type="submit" disabled={loading}>
          {loading ? "Please wait…" : mode === "login" ? "Sign in" : mode === "register" ? "Create account" : "Send reset link"}
        </button>

        {mode === "login" && (
          <>
            <button type="button" className="link" onClick={() => { reset(); setMode("register"); }}>
              Need an account? Register →
            </button>
            <button type="button" className="link" onClick={() => { reset(); setMode("forgot"); }}>
              Forgot your password?
            </button>
          </>
        )}
        {mode === "register" && (
          <button type="button" className="link" onClick={() => { reset(); setMode("login"); }}>
            Already have an account? Sign in →
          </button>
        )}
        {mode === "forgot" && (
          <button type="button" className="link" onClick={() => { reset(); setMode("login"); }}>
            ← Back to sign in
          </button>
        )}
      </form>
    </main>
  );
}
