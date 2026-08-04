"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Header from "@/components/Header";
import { api } from "@/lib/api";
import type { GameSummary, ModelConfig, Persona } from "@/lib/types";
import { useUser } from "@/lib/useUser";

export default function LobbyPage() {
  const { user, loading } = useUser();
  const router = useRouter();
  const [summary, setSummary] = useState<GameSummary | null>(null);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [seatFilter, setSeatFilter] = useState<number | null>(null);
  const [modelId, setModelId] = useState<number | null>(null);
  const [personaId, setPersonaId] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api<GameSummary>("/game/current");
      setSummary(data);
      if (data.game && data.game.status !== "lobby") {
        router.replace("/game");
      }
    } catch {
      /* ignore */
    }
  }, [router]);

  useEffect(() => {
    if (!user) return;
    load();
    const t = setInterval(load, 2000);
    api<{ models: ModelConfig[] }>("/admin/model-configs").then((d) => setModels(d.models)).catch(() => {});
    api<{ personas: Persona[] }>("/admin/ai-personas").then((d) => setPersonas(d.personas)).catch(() => {});
    return () => clearInterval(t);
  }, [user, load]);

  if (loading || !user) return <div className="min-h-screen" />;

  const game = summary?.game;
  const me = summary?.me;

  async function act(path: string, body?: any) {
    setError("");
    setBusy(true);
    try {
      await api(path, { method: "POST", body: JSON.stringify(body || {}) });
      await load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen">
      <Header user={user} />
      <main className="max-w-4xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">
            {game?.board_size}人局房间
            {game?.is_host && <span className="ml-2 text-sm text-amber-400">（你是房主）</span>}
          </h1>
          <button className="btn-ghost" onClick={() => router.push("/")}>
            ← 返回
          </button>
        </div>

        {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

        {/* 座位 */}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 mb-8">
          {summary?.players.map((p) => {
            const empty = p.controller_type === "empty";
            return (
              <div
                key={p.seat}
                className={`card p-4 relative ${empty ? "opacity-50 border-dashed" : ""} ${
                  seatFilter === p.seat ? "ring-2 ring-amber-400" : ""
                }`}
              >
                <div className="absolute top-2 right-2 text-xs text-slate-500">{p.seat}号</div>
                {p.is_host && <div className="text-[10px] text-amber-400 mb-1">🏠 房主</div>}
                {empty ? (
                  <div className="text-sm text-slate-500 mt-4 mb-2">空位</div>
                ) : (
                  <>
                    <div className="font-medium truncate mt-2">{p.name}</div>
                    <div className="text-xs text-slate-400 mt-1">
                      {p.controller_type === "human" ? "真人" : p.controller_type === "trustee" ? "AI托管" : "AI"}
                      {p.controller_type === "ai" && p.persona_name ? ` · ${p.persona_name}` : ""}
                    </div>
                  </>
                )}
                <div className="flex gap-1.5 mt-3">
                  {!empty && p.controller_type === "human" && p.user_id === user.id && (
                    <>
                      <button
                        className={`btn text-xs px-2 py-1 ${p.ready ? "btn-primary" : "btn-ghost"}`}
                        onClick={() => act("/game/current/ready", { ready: !p.ready })}
                      >
                        {p.ready ? "已准备 ✓" : "准备"}
                      </button>
                      <button className="btn-ghost text-xs px-2 py-1" onClick={() => act("/game/current/leave")}>
                        离开
                      </button>
                    </>
                  )}
                  {me === null && !empty && p.controller_type === "human" && (
                    <span className="text-xs text-slate-500 self-center">已就座</span>
                  )}
                  {game?.is_host && p.controller_type === "ai" && (
                    <button
                      className="btn-ghost text-xs px-2 py-1 text-red-300"
                      onClick={() => act("/game/current/ai-seats", { seat_number: p.seat, action: "remove" })}
                    >
                      移除
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* 我未入座时加入 */}
        {me === null && (
          <button className="btn-primary mb-6" onClick={() => act("/game/current/join")} disabled={busy}>
            加入游戏
          </button>
        )}

        {/* 房主 AI 配置 */}
        {game?.is_host && (
          <div className="card p-5 mb-6">
            <h2 className="font-bold mb-3">🤖 AI 座位配置</h2>
            <div className="flex flex-wrap items-end gap-3">
              <div>
                <label className="label">模型</label>
                <select
                  className="input w-48"
                  value={modelId ?? ""}
                  onChange={(e) => setModelId(e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">默认模型</option>
                  {models.filter((m) => m.enabled).map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.display_name}（{m.model_name}）
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">人格</label>
                <select
                  className="input w-44"
                  value={personaId ?? ""}
                  onChange={(e) => setPersonaId(e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">默认人格</option>
                  {personas.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex gap-2">
                <button className="btn-ghost" onClick={() => setSeatFilter(null)} disabled={busy}>
                  {seatFilter ? `向 ${seatFilter} 号添加 AI` : "选择空位添加 AI"}
                </button>
                <button
                  className="btn-primary"
                  disabled={busy}
                  onClick={() =>
                    act("/game/current/ai-fill", {
                      model_config_id: modelId,
                      persona_id: personaId,
                    })
                  }
                >
                  AI 补齐空位
                </button>
              </div>
            </div>
            {models.length === 0 && (
              <p className="text-xs text-amber-400 mt-2">
                尚未配置模型，请先由管理员在“模型配置”页添加
              </p>
            )}
          </div>
        )}

        <div className="flex justify-end">
          {game?.is_host && (
            <button
              className="btn-primary px-8 py-3"
              disabled={busy}
              onClick={() => act("/game/current/start")}
            >
              开始游戏
            </button>
          )}
        </div>
      </main>
    </div>
  );
}
