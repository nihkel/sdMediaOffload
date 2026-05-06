import { useState } from "react";
import { api } from "../lib/api";

export default function Login({ onLoggedIn }: { onLoggedIn: () => void }) {
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await api.login(password);
      onLoggedIn();
    } catch {
      setErr("Wrong password");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <form onSubmit={submit} className="panel p-8 w-full max-w-sm space-y-5">
        <div>
          <h1 className="text-xl font-semibold">SD Media Offload</h1>
          <p className="text-muted text-sm mt-1">Enter password to continue</p>
        </div>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoFocus
          className="input"
          placeholder="••••••••"
        />
        {err && <div className="text-rose-300 text-xs">{err}</div>}
        <button type="submit" disabled={busy || !password} className="btn btn-accent w-full justify-center">
          {busy ? "…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
