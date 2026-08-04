"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(username, password);
      router.replace("/");
    } catch (err: any) {
      setError(err.message || "登录失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="card w-full max-w-sm p-8">
        <h1 className="text-2xl font-bold text-center mb-1">🌙 AI狼人杀</h1>
        <p className="text-sm text-slate-400 text-center mb-6">真人 × 多模型 AI 的文字狼人杀</p>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="label">用户名</label>
            <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
          </div>
          <div>
            <label className="label">密码</label>
            <input
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error && <p className="text-red-400 text-sm">{error}</p>}
          <button className="btn-primary w-full" disabled={busy || !username || !password}>
            {busy ? "登录中…" : "登录"}
          </button>
        </form>
        <p className="mt-4 text-sm text-center text-slate-400">
          还没有账号？{" "}
          <Link href="/register" className="text-amber-400 hover:underline">
            注册
          </Link>
        </p>
      </div>
    </div>
  );
}
