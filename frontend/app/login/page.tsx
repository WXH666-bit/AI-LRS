"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";

const principles = [
  ["01", "读懂局势", "把每一次发言放回整场对局里。"],
  ["02", "听见异议", "让真人与不同人格的 AI 互相碰撞。"],
  ["03", "做出判断", "每一票都留下线索，也留下代价。"],
];

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
      setError(err.message || "登录失败，请检查账号和密码");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="relative min-h-screen overflow-hidden px-4 py-6 sm:px-8 lg:py-10">
      <div className="pointer-events-none absolute -left-32 top-20 h-80 w-80 rounded-full bg-gold/5 blur-3xl" />
      <div className="pointer-events-none absolute -right-40 bottom-0 h-[28rem] w-[28rem] rounded-full bg-cinnabar/5 blur-3xl" />

      <div className="relative mx-auto grid min-h-[calc(100vh-3rem)] max-w-6xl items-center gap-8 lg:grid-cols-[1.08fr_0.92fr] lg:gap-16">
        <section className="hidden lg:block">
          <div className="eyebrow mb-6">AI WEREWOLF · NIGHT TRIAL</div>
          <div className="max-w-xl">
            <div className="mb-7 flex items-center gap-4">
              <span className="flex h-16 w-16 items-center justify-center rounded-[22px] border border-gold/30 bg-gold/10 text-4xl text-gold shadow-[0_0_50px_rgb(200_155_60_/_14%)]">
                ☾
              </span>
              <div>
                <p className="text-sm font-medium tracking-[0.2em] text-smoke">欢迎进入</p>
                <h1 className="font-serif text-4xl font-semibold tracking-wide text-bone">AI 狼人杀</h1>
              </div>
            </div>
            <p className="font-serif text-5xl font-semibold leading-[1.12] tracking-tight text-bone">
              今夜，<span className="text-gold">谁在说谎</span>？
            </p>
            <p className="mt-6 max-w-lg text-base leading-8 text-smoke">
              真人 × 多模型 AI 的文字狼人杀。进入一场只靠发言、投票和直觉推进的暗夜审判。
            </p>
          </div>

          <div className="mt-14 grid max-w-xl gap-3">
            {principles.map(([number, title, text]) => (
              <div key={number} className="flex items-center gap-4 border-t border-white/10 py-4">
                <span className="font-mono text-xs text-gold/75">{number}</span>
                <span className="w-20 font-medium text-bone">{title}</span>
                <span className="text-sm text-smoke">{text}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="panel-elevated mx-auto w-full max-w-md p-6 sm:p-8">
          <div className="mb-8 lg:hidden">
            <div className="eyebrow mb-4">AI WEREWOLF · NIGHT TRIAL</div>
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl border border-gold/30 bg-gold/10 text-2xl text-gold">☾</span>
              <div>
                <h1 className="font-serif text-2xl font-semibold text-bone">AI 狼人杀</h1>
                <p className="mt-1 text-xs text-smoke">暗夜审判厅</p>
              </div>
            </div>
          </div>

          <div className="mb-7">
            <div className="eyebrow mb-2">ENTER THE TABLE</div>
            <h2 className="font-serif text-3xl font-semibold tracking-wide text-bone">登录对局</h2>
            <p className="mt-2 text-sm leading-6 text-smoke">准备好了吗？牌桌已经在等你。</p>
          </div>

          <form onSubmit={submit} className="space-y-5">
            <div>
              <label className="label" htmlFor="login-username">用户名</label>
              <input
                id="login-username"
                className="input"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
                autoComplete="username"
              />
            </div>
            <div>
              <label className="label" htmlFor="login-password">密码</label>
              <input
                id="login-password"
                className="input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </div>
            {error && (
              <div role="alert" className="rounded-xl border border-cinnabar/30 bg-cinnabar/10 px-3.5 py-3 text-sm leading-6 text-[#ef8f87]">
                <span className="mr-2" aria-hidden="true">!</span>
                {error}
              </div>
            )}
            <button className="btn-primary w-full py-3" disabled={busy || !username || !password} aria-busy={busy}>
              {busy ? "正在进入…" : "进入牌桌"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-smoke">
            还没有账号？{" "}
            <Link href="/register" className="focus-ring rounded text-gold hover:text-[#e7bd68] hover:underline">
              注册一个
            </Link>
          </p>
        </section>
      </div>
    </main>
  );
}
