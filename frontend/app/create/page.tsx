"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Header from "@/components/Header";
import EmptyState from "@/components/ui/EmptyState";
import StatusBadge from "@/components/ui/StatusBadge";
import { api } from "@/lib/api";
import { useUser } from "@/lib/useUser";

const BOARDS = [
  { size: 6, name: "6 人局", desc: "2 狼人 · 1 预言家 · 1 女巫 · 2 平民", tag: "无警长 · 快速局", mood: "适合第一次上桌" },
  { size: 9, name: "9 人局", desc: "3 狼人 · 1 预言家 · 1 女巫 · 1 猎人 · 3 平民", tag: "启用警长 · 经典局", mood: "信息与博弈的平衡" },
  { size: 12, name: "12 人局", desc: "4 狼人 · 1 预言家 · 1 女巫 · 1 猎人 · 1 守卫 · 4 平民", tag: "启用警长 · 标准局", mood: "留给老练玩家的长局" },
];

export default function CreatePage() {
  const { user, loading } = useUser();
  const router = useRouter();
  const [selected, setSelected] = useState(9);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function create() {
    setError("");
    setBusy(true);
    try {
      await api("/game/current", { method: "POST", body: JSON.stringify({ board_size: selected }) });
      router.push("/lobby");
    } catch (err: any) {
      setError(err.message || "创建失败，请稍后重试");
      setBusy(false);
    }
  }

  if (loading || !user) return <div className="min-h-screen" />;

  return (
    <div className="min-h-screen">
      <Header user={user} />
      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:py-12">
        <div className="mb-10 max-w-2xl">
          <div className="eyebrow mb-3">OPEN A NEW TABLE</div>
          <h1 className="font-serif text-4xl font-semibold tracking-tight text-bone">选择你的审判规模</h1>
          <p className="mt-3 text-sm leading-7 text-smoke">不同人数代表不同的信息密度。选好阵容，下一步进入大厅安排 AI 与人格。</p>
        </div>

        <div className="grid gap-4 lg:grid-cols-3">
          {BOARDS.map((board) => {
            const selectedCard = selected === board.size;
            return (
              <button
                key={board.size}
                type="button"
                role="radio"
                aria-checked={selectedCard}
                onClick={() => setSelected(board.size)}
                className={`focus-ring group relative overflow-hidden rounded-[20px] border p-5 text-left transition-all duration-200 sm:p-6 ${
                  selectedCard
                    ? "border-gold/70 bg-gold/10 shadow-[0_18px_45px_rgb(200_155_60_/_14%)]"
                    : "border-white/10 bg-ink-800/75 hover:-translate-y-1 hover:border-gold/35 hover:bg-ink-800"
                }`}
              >
                <div className="absolute right-5 top-5 font-mono text-5xl font-semibold text-white/5">{board.size}</div>
                <div className="relative">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-serif text-2xl font-semibold text-bone">{board.name}</span>
                    {selectedCard && <StatusBadge tone="gold">已选择</StatusBadge>}
                  </div>
                  <p className="mt-5 min-h-[48px] text-sm leading-6 text-smoke">{board.desc}</p>
                  <div className="mt-6 border-t border-white/10 pt-4">
                    <div className="text-xs font-semibold text-[#e7bd68]">{board.tag}</div>
                    <div className="mt-1 text-xs text-smoke/75">{board.mood}</div>
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        <div className="mt-8 max-w-2xl">
          {error && <div role="alert" className="mb-4 rounded-xl border border-cinnabar/30 bg-cinnabar/10 px-4 py-3 text-sm text-[#ef8f87]">{error}</div>}
          <button className="btn-primary w-full py-3.5 sm:w-auto sm:px-10" disabled={busy} onClick={create} aria-busy={busy}>
            {busy ? "正在创建…" : "创建并进入房间"}
          </button>
        </div>
      </main>
    </div>
  );
}
