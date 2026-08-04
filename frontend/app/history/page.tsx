"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Header from "@/components/Header";
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
      <main className="max-w-4xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-6">历史对局</h1>
        {games.length === 0 && <p className="text-slate-500">暂无已结束的对局</p>}
        <div className="space-y-3">
          {games.map((g) => (
            <Link key={g.id} href={`/history/${g.id}`} className="card p-5 flex items-center justify-between hover:border-amber-400/50 transition-colors">
              <div>
                <div className="font-bold">
                  {g.board_size}人局
                  <span className={`ml-3 text-sm ${g.winner === "good" ? "text-sky-300" : "text-red-300"}`}>
                    {g.winner === "good" ? "🏆 好人获胜" : "🐺 狼人获胜"}
                  </span>
                </div>
                <div className="text-xs text-slate-500 mt-1">
                  {g.end_reason} · 结束于 {g.ended_at?.replace("T", " ").slice(0, 16)}
                </div>
              </div>
              <span className="text-slate-400 text-sm">查看回放 →</span>
            </Link>
          ))}
        </div>
      </main>
    </div>
  );
}
