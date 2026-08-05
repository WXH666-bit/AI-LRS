"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import Header from "@/components/Header";
import { api } from "@/lib/api";
import { formatEvent, roleLabel, type DisplayLine } from "@/lib/formatEvent";
import type { GameEvent } from "@/lib/types";
import { useUser } from "@/lib/useUser";

interface ReplayData {
  game: {
    id: number;
    board_size: number;
    winner: string | null;
    end_reason: string | null;
    created_at: string | null;
    ended_at: string | null;
  };
  roles: Record<number, string>;
  events: GameEvent[];
}

export default function ReplayPage() {
  const { user, loading } = useUser();
  const params = useParams<{ id: string }>();
  const [data, setData] = useState<ReplayData | null>(null);
  const [shown, setShown] = useState(50);

  useEffect(() => {
    if (!user) return;
    api<ReplayData>(`/games/${params.id}/replay`).then(setData).catch(() => {});
  }, [user, params.id]);

  const lines = useMemo(() => {
    if (!data) return [];
    return data.events
      .map((e) => {
        const line = formatEvent(e);
        return line ? { ...line, raw: e } : null;
      })
      .filter((l): l is DisplayLine & { raw: GameEvent } => l !== null)
      // 相邻重复的阶段行只保留一条（每个行动窗口都会发 phase_change）
      .filter((l, i, arr) => !(l.kind === "phase" && i > 0 && arr[i - 1].kind === "phase" && arr[i - 1].text === l.text));
  }, [data]);

  const roles = useMemo(
    () => Object.entries(data?.roles || {}).sort((a, b) => Number(a[0]) - Number(b[0])),
    [data]
  );

  if (loading || !user) return <div className="min-h-screen" />;
  if (!data) return <div className="min-h-screen"><Header user={user} /></div>;

  return (
    <div className="min-h-screen">
      <Header user={user} />
      <main className="max-w-5xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">
            回放 · {data.game.board_size}人局
            <span className={`ml-3 text-base ${data.game.winner === "good" ? "text-sky-300" : data.game.winner === "wolf" ? "text-red-300" : "text-slate-400"}`}>
              {data.game.winner === "good" ? "🏆 好人阵营获胜" : data.game.winner === "wolf" ? "🐺 狼人阵营获胜" : "⏹️ 已结束"}
            </span>
          </h1>
          <Link href="/history" className="btn-ghost">
            ← 返回
          </Link>
        </div>

        {/* 身份揭晓 */}
        <div className="card p-5 mb-6">
          <h2 className="font-bold mb-3">身份一览</h2>
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2">
            {roles.map(([seat, role]) => (
              <div key={seat} className="bg-night-900 rounded px-3 py-2 text-center">
                <div className="text-xs text-slate-400">{seat}号</div>
                <div className={`text-sm ${role === "wolf" ? "text-red-300" : "text-emerald-300"}`}>{roleLabel(role)}</div>
              </div>
            ))}
          </div>
        </div>

        {/* 事件时间线（全部事件，含夜间行动与狼人私聊） */}
        <div className="card p-5">
          <h2 className="font-bold mb-3">完整事件时间线</h2>
          <div className="space-y-1.5 text-sm max-h-[60vh] overflow-y-auto">
            {lines.slice(0, shown).map((l) => (
              <div key={l.seq} className={l.kind === "wolf" ? "text-purple-300" : l.kind === "death" ? "text-red-400" : l.kind === "phase" ? "text-amber-400 font-bold text-center" : l.kind === "private" ? "text-emerald-300" : "text-moon"}>
                {l.text}
              </div>
            ))}
          </div>
          {lines.length > shown && (
            <button className="btn-ghost w-full mt-4" onClick={() => setShown((n) => n + 200)}>
              加载更多（{lines.length - shown} 条）
            </button>
          )}
        </div>
      </main>
    </div>
  );
}
