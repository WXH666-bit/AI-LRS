"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { login, register } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (password !== confirm) {
      setError("两次输入的密码不一致");
      return;
    }
    setBusy(true);
    try {
      await register(username, password);
      await login(username, password);
      router.replace("/");
    } catch (err: any) {
      setError(err.message || "注册失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="card w-full max-w-sm p-8">
        <h1 className="text-2xl font-bold text-center mb-6">注册账号</h1>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="label">用户名（3~32位，字母数字下划线）</label>
            <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
          </div>
          <div>
            <label className="label">密码（至少6位）</label>
            <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          <div>
            <label className="label">确认密码</label>
            <input className="input" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </div>
          {error && <p className="text-red-400 text-sm">{error}</p>}
          <button className="btn-primary w-full" disabled={busy || !username || !password}>
            {busy ? "注册中…" : "注册"}
          </button>
        </form>
        <p className="mt-4 text-sm text-center text-slate-400">
          已有账号？{" "}
          <Link href="/login" className="text-amber-400 hover:underline">
            登录
          </Link>
        </p>
      </div>
    </div>
  );
}
