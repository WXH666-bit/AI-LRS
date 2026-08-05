"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Header from "@/components/Header";
import EmptyState from "@/components/ui/EmptyState";
import Panel from "@/components/ui/Panel";
import StatusBadge from "@/components/ui/StatusBadge";
import { api } from "@/lib/api";
import { useUser } from "@/lib/useUser";

interface HistoryGame {
  id: number;
  board_size: number;
  status: string;
  phase: string;
  winner: string | null;
  end_reason: string | null;
  created_at: string | null;
  ended_at: string | null;
  is_host: boolean;
}

export default function HistoryPage() {
  const { user, loading } = useUser();
  const [games, setGames] = useState<HistoryGame[]>([]);

  useEffect(() => {
    if (!user) return;
    api<{ games: HistoryGame[] }>("/games/history").then((d) => setGames(d.games)).catch(() => {});
  }, [user]);

  if (loading || !user) return <div className="min-h-screen" />;

  return (
    <div className="min-h-screen">
      <Header user={user} />
      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:py-12">
        <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <div className="eyebrow mb-3">THE ARCHIVE</div>
            <h1 className="font-serif text-4xl font-semibold tracking-tight text-bone">历史对局</h1>
            <p className="mt-2 text-sm text-smoke">每一场结束的对局，都会留下可回看的证词。</p>
          </div>
          <Link href="/create" className="btn-primary w-fit">创建新对局</Link>
        </div>

        {games.length === 0 ? (
          <EmptyState
            eyebrow="NO CASE FILES"
            title="还没有结束的对局"
            description="当第一场审判结束后，它的发言、投票和身份都会出现在这里。"
            action={<Link href="/create" className="btn-primary">开始第一场对局</Link>}
          />
        ) : (
          <div className="space-y-3">
            {games.map((game) => (
              <Link key={game.id} href={`/history/${game.id}`} className="focus-ring block rounded-[18px]">
                <Panel className="group p-5 transition-all duration-200 hover:-translate-y-0.5 hover:border-gold/35 hover:bg-ink-800 sm:p-6">
                  <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-center">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-3">
                        <span className="font-serif text-xl font-semibold text-bone">{game.board_size} 人局</span>
                        <StatusBadge tone={game.winner === "wolf" ? "danger" : game.winner === "good" ? "success" : "muted"}>
                          {game.winner === "good" ? "好人阵营获胜" : game.winner === "wolf" ? "狼人阵营获胜" : "对局结束"}
                        </StatusBadge>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-smoke">
                        <span>{game.end_reason || "正常结束"}</span>
                        <span>结束于 {game.ended_at?.replace("T", " ").slice(0, 16) || "未知时间"}</span>
                      </div>
                    </div>
                    <span className="shrink-0 text-sm font-semibold text-gold transition-transform group-hover:translate-x-1">查看回放 →</span>
                  </div>
                </Panel>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
