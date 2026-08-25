"use client";

import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type AdminUser = {
  id: number;
  email: string;
  display_name: string;
  is_verified: boolean;
  created_at: string;
  practice_attempts: number;
  standards_started: number;
};

export default function AdminPage() {
  const [key, setKey] = useState("");
  const [entered, setEntered] = useState(false);
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async (adminKey: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/admin/users`, {
        headers: { "X-Admin-Key": adminKey },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Request failed (${res.status})`);
      }
      const data = await res.json();
      setUsers(data);
      setEntered(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load users.");
      setEntered(false);
    } finally {
      setLoading(false);
    }
  };

  if (!entered) {
    return (
      <main style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#0f0f14" }}>
        <div style={{ background: "#1a1a22", padding: 32, borderRadius: 16, width: 360, color: "#fff" }}>
          <h2 style={{ marginBottom: 8 }}>Admin access</h2>
          <p style={{ color: "#999", fontSize: 14, marginBottom: 20 }}>Enter the admin key to view registered students.</p>
          <input
            type="password"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && key.trim()) load(key.trim()); }}
            placeholder="Admin key"
            style={{ width: "100%", padding: 10, borderRadius: 8, border: "1px solid #333", marginBottom: 12, background: "#0f0f14", color: "#fff" }}
          />
          {error && <div style={{ color: "#ff6b6b", fontSize: 13, marginBottom: 12 }}>{error}</div>}
          <button
            onClick={() => key.trim() && load(key.trim())}
            disabled={loading || !key.trim()}
            style={{ width: "100%", padding: 10, borderRadius: 8, border: "none", background: "#6c5ce7", color: "#fff", fontWeight: 600, cursor: "pointer" }}
          >
            {loading ? "Checking…" : "Enter"}
          </button>
        </div>
      </main>
    );
  }

  return (
    <main style={{ minHeight: "100vh", background: "#0f0f14", color: "#fff", padding: 32 }}>
      <div style={{ maxWidth: 900, margin: "0 auto" }}>
        <h1 style={{ marginBottom: 4 }}>Registered students</h1>
        <p style={{ color: "#999", marginBottom: 24 }}>{users?.length ?? 0} total</p>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ textAlign: "left", borderBottom: "1px solid #333" }}>
                <th style={{ padding: "10px 8px" }}>Name</th>
                <th style={{ padding: "10px 8px" }}>Email</th>
                <th style={{ padding: "10px 8px" }}>Verified</th>
                <th style={{ padding: "10px 8px" }}>Registered</th>
                <th style={{ padding: "10px 8px" }}>Practice attempts</th>
                <th style={{ padding: "10px 8px" }}>Standards started</th>
              </tr>
            </thead>
            <tbody>
              {users?.map((u) => (
                <tr key={u.id} style={{ borderBottom: "1px solid #222" }}>
                  <td style={{ padding: "10px 8px" }}>{u.display_name}</td>
                  <td style={{ padding: "10px 8px" }}>{u.email}</td>
                  <td style={{ padding: "10px 8px" }}>{u.is_verified ? "✅" : "—"}</td>
                  <td style={{ padding: "10px 8px" }}>{new Date(u.created_at).toLocaleString()}</td>
                  <td style={{ padding: "10px 8px" }}>{u.practice_attempts}</td>
                  <td style={{ padding: "10px 8px" }}>{u.standards_started}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
