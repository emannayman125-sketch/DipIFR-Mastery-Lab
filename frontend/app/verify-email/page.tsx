"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "../lib/api";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [status, setStatus] = useState<"loading" | "done" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setMessage("This verification link is missing its token.");
      return;
    }
    api
      .verifyEmail(token)
      .then((res) => {
        setStatus("done");
        setMessage(res.detail);
      })
      .catch((err) => {
        setStatus("error");
        setMessage(err instanceof ApiError ? err.message : "This link may have expired.");
      });
  }, [token]);

  return (
    <main className="authShell">
      <div className="authCard">
        <h2>{status === "loading" ? "Verifying…" : status === "done" ? "Email verified" : "Verification failed"}</h2>
        <p className="lead">{status === "loading" ? "One moment…" : message}</p>
        {status !== "loading" && (
          <Link className="primary" href="/" style={{ textAlign: "center", display: "block" }}>Go to sign in</Link>
        )}
      </div>
    </main>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<main className="authShell"><p style={{ color: "#fff" }}>Loading…</p></main>}>
      <VerifyEmailContent />
    </Suspense>
  );
}
