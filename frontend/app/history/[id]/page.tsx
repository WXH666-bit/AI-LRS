"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import Header from "@/components/Header";
import Panel from "@/components/ui/Panel";
import StatusBadge from "@/components/ui/StatusBadge";
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

const eventClasses: Record<DisplayLine["kind"], string> = {
  phase: "border-gold/25 bg-gold/5 text-[#e7bd68] text-center font-semibold",
  public: "border-white/8 bg-white/[0.02] text-bone",
  wolf: "border-[#9b78c5]/25 bg-[#9b78c5]/5 text-[#c9b6e4]",
  private: "border-sage/25 bg-sage/5 text-[#9bd3c6]",
  death: "border-cinnabar/25 bg-cinnabar/5 text-[#ef8f87]",
  system: "border-sky-300/20 bg-sky-300/5 text-sky-200",
  me: "border-gold/25 bg-gold/5 text-[#e7bd68]",
};

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
      .map((event) => {
        const line = formatEvent(event);
        return line ? { ...line, raw: event } : null;
      })
      .filter((line): line is DisplayLine & { raw: GameEvent } => line !== null)
      .filter((line, index, array) => !(line.kind === "phase" && index > 0 && array[index - 1].kind === "phase" && array[index - 1].text === line.text));
  }, [data]);

  const roles = useMemo(() => Object.entries(data?.roles || {}).sort((a, b) => Number(a[0]) - Number(b[0])), [data]);

  if (loading || !user) return <div className="min-h-screen" />;
  if (!data) return <div className="min-h-screen"><Header user={user} /></div>;

  const winnerTone = data.game.winner === "wolf" ? "danger" : data.game.winner === "good" ? "success" : "muted";

  return (
    <div className="min-h-screen">
      <Header user={user} />
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:py-12">
        <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <div className="eyebrow mb-3">CASE FILE #{String(data.game.id).padStart(2, "0")}</div>
            <h1 className="font-serif text-4xl font-semibold tracking-tight text-bone">{data.game.board_size} 人局回放</h1>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <StatusBadge tone={winnerTone}>
                {data.game.winner === "good" ? "好人阵营获胜" : data.game.winner === "wolf" ? "狼人阵营获胜" : "对局结束"}
              </StatusBadge>
              <span className="text-sm text-smoke">{data.game.end_reason || "正常结束"}</span>
            </div>
          </div>
          <Link href="/history" className="btn-ghost w-fit">← 返回历史</Link>
        </div>

        <div className="grid gap-6 xl:grid-cols-[280px_minmax(0,1fr)]">
          <Panel className="h-fit p-5 sm:p-6" title={<><div className="eyebrow mb-2">IDENTITIES</div><h2 className="font-serif text-xl font-semibold text-bone">身份揭晓</h2></>}>
            <div className="mt-5 grid grid-cols-2 gap-2">
              {roles.map(([seat, role]) => (
                <div key={seat} className="rounded-xl border border-white/10 bg-ink-900/65 px-3 py-3">
                  <div className="font-mono text-[10px] text-gold">{String(seat).padStart(2, "0")} 号</div>
                  <div className={`mt-2 text-sm font-medium ${role === "wolf" ? "text-[#ef8f87]" : "text-[#9bd3c6]"}`}>{roleLabel(role)}</div>
                </div>
              ))}
            </div>
          </Panel>

          <Panel className="overflow-hidden">
            <div className="border-b border-white/10 px-5 py-4 sm:px-6">
              <div className="eyebrow mb-2">EVIDENCE TIMELINE</div>
              <div className="flex items-end justify-between gap-3">
                <h2 className="font-serif text-xl font-semibold text-bone">完整事件时间线</h2>
                <span className="text-xs text-smoke">共 {lines.length} 条记录</span>
              </div>
            </div>
            <div className="max-h-[65vh] space-y-2 overflow-y-auto p-4 sm:p-6">
              {lines.slice(0, shown).map((line) => (
                <div key={line.seq} className={`rounded-xl border px-3.5 py-2.5 text-sm leading-6 ${eventClasses[line.kind]}`}>
                  {line.text}
                </div>
              ))}
            </div>
            {lines.length > shown && (
              <div className="border-t border-white/10 p-4">
                <button className="btn-ghost w-full" onClick={() => setShown((count) => count + 200)}>
                  加载更多（剩余 {lines.length - shown} 条）
                </button>
              </div>
            )}
          </Panel>
        </div>
      </main>
    </div>
  );
}
