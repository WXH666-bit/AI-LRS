"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Header from "@/components/Header";
import EmptyState from "@/components/ui/EmptyState";
import Panel from "@/components/ui/Panel";
import StatusBadge from "@/components/ui/StatusBadge";
import { api } from "@/lib/api";
import type { GameSummary } from "@/lib/types";
import { useUser } from "@/lib/useUser";

const STATUS_LABELS: Record<string, string> = {
  lobby: "房间准备中",
  running: "对局进行中",
  paused: "对局已暂停",
  ended: "对局已结束",
};

function statusTone(status: string): "gold" | "danger" | "success" | "info" | "muted" {
  if (status === "running") return "success";
  if (status === "paused") return "danger";
  if (status === "ended") return "muted";
  return "gold";
}

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
        /* The empty console remains useful when the API is unavailable. */
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [user]);

  if (loading || !user) return <div className="min-h-screen" />;

  const game = summary?.game;
  const aliveCount = summary?.players.filter((player) => player.alive).length ?? 0;

  return (
    <div className="min-h-screen">
      <Header user={user} />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:py-12">
        {!game ? (
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px] xl:items-stretch">
            <section className="relative overflow-hidden rounded-[24px] border border-gold/20 bg-ink-800/80 px-6 py-10 shadow-[0_24px_80px_rgb(0_0_0_/_22%)] sm:px-10 sm:py-14">
              <div className="pointer-events-none absolute -right-20 -top-24 h-72 w-72 rounded-full bg-gold/10 blur-3xl" />
              <div className="relative max-w-2xl">
                <div className="eyebrow mb-5">THE TABLE IS QUIET</div>
                <h1 className="font-serif text-4xl font-semibold leading-tight tracking-tight text-bone sm:text-6xl">
                  今夜，谁在说谎？
                </h1>
                <p className="mt-5 max-w-xl text-base leading-8 text-smoke">
                  创建一场属于你的暗夜审判。让真人玩家和不同人格的 AI 坐上同一张牌桌，用发言、投票和直觉找出狼人。
                </p>
                <div className="mt-8 flex flex-wrap items-center gap-3">
                  <Link href="/create" className="btn-primary px-6 py-3">创建对局</Link>
                  <Link href="/history" className="btn-ghost px-5 py-3">查看历史</Link>
                </div>
              </div>
            </section>
            <Panel className="flex flex-col justify-between p-6">
              <div>
                <div className="eyebrow mb-3">HOW IT WORKS</div>
                <h2 className="font-serif text-2xl font-semibold text-bone">一张牌桌，三种判断</h2>
              </div>
              <div className="mt-8 space-y-4">
                {[
                  ["01", "听见发言", "每句话都可能是线索。"],
                  ["02", "观察投票", "立场会在关键时刻显形。"],
                  ["03", "留下判断", "让下一轮的局势更清晰。"],
                ].map(([number, title, text]) => (
                  <div key={number} className="flex gap-3 border-t border-white/10 pt-4">
                    <span className="font-mono text-xs text-gold">{number}</span>
                    <div>
                      <div className="text-sm font-semibold text-bone">{title}</div>
                      <div className="mt-1 text-xs leading-5 text-smoke">{text}</div>
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
          </div>
        ) : (
          <div className="space-y-6">
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
              <div>
                <div className="eyebrow mb-3">CURRENT TABLE</div>
                <h1 className="font-serif text-4xl font-semibold tracking-tight text-bone">当前对局</h1>
                <p className="mt-2 text-sm text-smoke">一切判断，都从这张牌桌开始。</p>
              </div>
              <StatusBadge tone={statusTone(game.status)}>{STATUS_LABELS[game.status] || game.status}</StatusBadge>
            </div>

            <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
              <Panel className="overflow-hidden">
                <div className="border-b border-white/10 bg-gradient-to-br from-gold/10 via-transparent to-transparent p-6 sm:p-8">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <div className="eyebrow mb-3">TABLE {String(game.id).padStart(2, "0")}</div>
                      <h2 className="font-serif text-3xl font-semibold text-bone">{game.board_size} 人局</h2>
                      <p className="mt-2 text-sm text-smoke">{game.status === "ended" ? game.end_reason : "牌桌正在等待下一步判断"}</p>
                    </div>
                    {game.winner && (
                      <StatusBadge tone={game.winner === "wolf" ? "danger" : "success"}>
                        {game.winner === "good" ? "好人阵营获胜" : "狼人阵营获胜"}
                      </StatusBadge>
                    )}
                  </div>
                  <div className="mt-8 flex flex-wrap gap-2 text-xs text-smoke">
                    <span className="rounded-full border border-white/10 bg-ink-900/60 px-3 py-1.5">{summary?.players.length || 0} 个席位</span>
                    <span className="rounded-full border border-white/10 bg-ink-900/60 px-3 py-1.5">{aliveCount} 人存活</span>
                    {game.is_host && <span className="rounded-full border border-gold/25 bg-gold/10 px-3 py-1.5 text-[#e7bd68]">你是房主</span>}
                  </div>
                </div>

                <div className="p-6 sm:p-8">
                  {game.status === "lobby" && (
                    <button className="btn-primary w-full py-3.5" onClick={() => router.push("/lobby")}>进入房间</button>
                  )}
                  {(game.status === "running" || game.status === "paused") && (
                    <button className="btn-primary w-full py-3.5" onClick={() => router.push("/game")}>
                      {game.status === "paused" ? "进入对局（已暂停）" : "进入对局"}{summary?.me ? "" : "（观战）"}
                    </button>
                  )}
                  {game.status === "ended" && (
                    <div className="space-y-3">
                      <p className="text-sm text-smoke">结束于 {game.ended_at?.replace("T", " ").slice(0, 16)}</p>
                      <Link href={`/history/${game.id}`} className="btn-ghost w-full py-3">查看结算与回放</Link>
                      <Link href="/create" className="btn-primary w-full py-3">创建新对局</Link>
                    </div>
                  )}
                </div>
              </Panel>

              <Panel className="p-5 sm:p-6" title={<><div className="eyebrow mb-2">SEAT MAP</div><h2 className="font-serif text-xl font-semibold text-bone">牌桌座位</h2></>}>
                <div className="mt-1 grid grid-cols-2 gap-2">
                  {summary?.players.map((player) => (
                    <div key={player.seat} className={`rounded-xl border px-3 py-3 ${player.alive ? "border-white/10 bg-ink-900/65" : "border-white/5 bg-ink-900/35 opacity-55"}`}>
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-[10px] text-gold">{String(player.seat).padStart(2, "0")}</span>
                        <StatusBadge tone={player.alive ? "success" : "muted"} className="px-1.5 py-0.5 text-[9px]">
                          {player.alive ? "存活" : "出局"}
                        </StatusBadge>
                      </div>
                      <div className="mt-2 truncate text-sm font-medium text-bone">{player.name}</div>
                      <div className="mt-1 text-[10px] text-smoke">{player.controller_type === "human" ? "真人" : player.controller_type === "trustee" ? "AI 托管" : "AI"}</div>
                    </div>
                  ))}
                </div>
              </Panel>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
