"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Header from "@/components/Header";
import { api } from "@/lib/api";
import { useUser } from "@/lib/useUser";

const BOARDS = [
  {
    size: 6,
    name: "6人局",
    desc: "2狼人 · 1预言家 · 1女巫 · 2平民",
    tag: "无警长 · 快速局",
  },
  {
    size: 9,
    name: "9人局",
    desc: "3狼人 · 1预言家 · 1女巫 · 1猎人 · 3平民",
    tag: "启用警长 · 经典局",
  },
  {
    size: 12,
    name: "12人局",
    desc: "4狼人 · 1预言家 · 1女巫 · 1猎人 · 1守卫 · 4平民",
    tag: "启用警长 · 标准局",
  },
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
      setError(err.message || "创建失败");
      setBusy(false);
    }
  }

  if (loading || !user) return <div className="min-h-screen" />;

  return (
    <div className="min-h-screen">
      <Header user={user} />
      <main className="max-w-2xl mx-auto px-4 py-10">
        <h1 className="text-2xl font-bold mb-6">创建对局</h1>
        <div className="space-y-4">
          {BOARDS.map((b) => (
            <button
              key={b.size}
              onClick={() => setSelected(b.size)}
              className={`card w-full p-5 text-left transition-all ${
                selected === b.size ? "ring-2 ring-amber-400" : "hover:border-night-500"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-lg font-bold">{b.name}</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-night-700 text-amber-300">{b.tag}</span>
              </div>
              <p className="text-sm text-slate-400 mt-1">{b.desc}</p>
            </button>
          ))}
        </div>
        {error && <p className="text-red-400 text-sm mt-4">{error}</p>}
        <button className="btn-primary w-full py-3 mt-6" disabled={busy} onClick={create}>
          {busy ? "创建中…" : "创建并进入房间"}
        </button>
      </main>
    </div>
  );
}
