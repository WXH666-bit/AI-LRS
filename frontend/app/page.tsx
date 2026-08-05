"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Header from "@/components/Header";
import { api, type UserInfo } from "@/lib/api";
import type { GameSummary } from "@/lib/types";
import { useUser } from "@/lib/useUser";

const STATUS_LABELS: Record<string, string> = {
  lobby: "房间准备中",
  running: "对局进行中",
  paused: "已暂停",
  ended: "对局已结束",
};

export default function HomePage() {
  const { user, loading } = useUser();
  const router = useRouter();
  const [summary, setSummary] = useState<GameSummary | null>(null);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    async function load() {
      try {
        const data = await api<GameSummary>("/game/current");
        if (!cancelled) setSummary(data);
      } catch {
        /* ignore */
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [user]);

  if (loading || !user) return <div className="min-h-screen" />;

  const game = summary?.game;

  return (
    <div className="min-h-screen">
      <Header user={user} />
      <main className="max-w-3xl mx-auto px-4 py-10">
        {!game && (
          <div className="text-center py-16">
            <h1 className="text-3xl font-bold mb-3">🌙 AI 狼人杀</h1>
            <p className="text-slate-400 mb-8">当前没有对局，创建一个开始游戏吧</p>
            <Link href="/create" className="btn-primary text-base px-8 py-3">
              ＋ 创建对局
            </Link>
            <div className="mt-6 text-sm text-slate-500">
              <Link href="/history" className="text-amber-400 hover:underline">
                查看历史对局
              </Link>
            </div>
          </div>
        )}

        {game && (
          <div className="card p-8">
            <div className="flex items-center justify-between mb-6">
              <h1 className="text-xl font-bold">
                {game.board_size}人局 · <span className="text-amber-400">{STATUS_LABELS[game.status]}</span>
              </h1>
              {game.winner ? (
                <span className="text-sm">
                  {game.winner === "good" ? "🏆 好人阵营获胜" : "🐺 狼人阵营获胜"}
                  {game.is_host && <span className="ml-2 text-amber-400 text-xs">你是房主</span>}
                </span>
              ) : (
                game.status === "ended" && <span className="text-sm text-slate-400">⏹️ 对局已结束</span>
              )}
            </div>

            {game.status === "lobby" && (
              <button className="btn-primary w-full py-3" onClick={() => router.push("/lobby")}>
                进入房间
              </button>
            )}
            {game.status === "running" && (
              <button className="btn-primary w-full py-3" onClick={() => router.push("/game")}>
                进入对局{summary?.me ? "" : "（观战）"}
              </button>
            )}
            {game.status === "paused" && (
              <button className="btn-primary w-full py-3" onClick={() => router.push("/game")}>
                进入对局（已暂停）{summary?.me ? "" : "（观战）"}
              </button>
            )}
            {game.status === "ended" && (
              <div className="space-y-3">
                <p className="text-sm text-slate-400">
                  {game.end_reason} · 结束于 {game.ended_at?.replace("T", " ").slice(0, 16)}
                </p>
                <Link href={`/history/${game.id}`} className="btn-ghost w-full">
                  查看结算与回放
                </Link>
                <Link href="/create" className="btn-primary w-full">
                  创建新对局
                </Link>
              </div>
            )}

            {summary && summary.players.length > 0 && (
              <div className="mt-6 grid grid-cols-3 sm:grid-cols-4 gap-3">
                {summary.players.map((p) => (
                  <div
                    key={p.seat}
                    className={`rounded-lg border px-3 py-2 text-center ${
                      p.alive ? "border-night-600 bg-night-900" : "border-slate-800 bg-night-900/50 opacity-60"
                    }`}
                  >
                    <div className="text-xs text-slate-400">{p.seat}号</div>
                    <div className="text-sm truncate">{p.name}</div>
                    <div className="text-[10px] text-slate-500">
                      {p.controller_type === "human" ? "真人" : p.controller_type === "trustee" ? "AI托管" : "AI"}
                      {game.status === "ended" && p.role && ` · ${p.role === "wolf" ? "🐺狼人" : "好人"}`}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
