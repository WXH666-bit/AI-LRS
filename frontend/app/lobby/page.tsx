"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Header from "@/components/Header";
import Panel from "@/components/ui/Panel";
import StatusBadge from "@/components/ui/StatusBadge";
import SeatCard from "@/components/game/SeatCard";
import { api } from "@/lib/api";
import type { GameSummary, ModelConfig, Persona } from "@/lib/types";
import { useUser } from "@/lib/useUser";

interface SeatCfg {
  modelId: number | null;
  personaId: number | null;
}

export default function LobbyPage() {
  const { user, loading } = useUser();
  const router = useRouter();
  const [summary, setSummary] = useState<GameSummary | null>(null);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [seatCfg, setSeatCfg] = useState<Record<number, SeatCfg>>({});
  const [fillModelId, setFillModelId] = useState<number | null>(null);
  const [fillPersonaId, setFillPersonaId] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api<GameSummary>("/game/current");
      setSummary(data);
      if (data.game && data.game.status !== "lobby") router.replace("/game");
    } catch {
      /* ignore */
    }
  }, [router]);

  useEffect(() => {
    if (!user) return;
    load();
    const timer = setInterval(load, 2000);
    api<{ models: ModelConfig[] }>("/admin/model-configs").then((data) => setModels(data.models)).catch(() => {});
    api<{ personas: Persona[] }>("/admin/ai-personas").then((data) => setPersonas(data.personas)).catch(() => {});
    return () => clearInterval(timer);
  }, [user, load]);

  if (loading || !user) return <div className="min-h-screen" />;

  const game = summary?.game;
  const me = summary?.me;
  const enabledModels = models.filter((model) => model.enabled);

  async function act(path: string, body?: any) {
    setError("");
    setBusy(true);
    try {
      await api(path, { method: "POST", body: JSON.stringify(body || {}) });
      await load();
    } catch (err: any) {
      setError(err.message || "操作失败，请稍后重试");
    } finally {
      setBusy(false);
    }
  }

  function cfgOf(seat: number): SeatCfg {
    return seatCfg[seat] ?? { modelId: null, personaId: null };
  }

  function setCfg(seat: number, patch: Partial<SeatCfg>) {
    setSeatCfg((previous) => ({ ...previous, [seat]: { ...cfgOf(seat), ...patch } }));
  }

  function addAI(seat: number) {
    const { modelId, personaId } = cfgOf(seat);
    act("/game/current/ai-seats", { seat_number: seat, action: "add", model_config_id: modelId, persona_id: personaId });
  }

  function updateAI(seat: number) {
    const { modelId, personaId } = cfgOf(seat);
    act("/game/current/ai-seats", { seat_number: seat, action: "update", model_config_id: modelId, persona_id: personaId });
  }

  function modelName(id: number | null | undefined): string {
    if (!id) return "默认模型";
    return models.find((model) => model.id === id)?.display_name || `模型#${id}`;
  }

  function personaName(fallback?: string | null): string {
    return fallback || "自由发挥";
  }

  return (
    <div className="min-h-screen">
      <Header user={user} />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:py-12">
        <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <div className="eyebrow mb-3">THE LOBBY</div>
            <h1 className="font-serif text-4xl font-semibold tracking-tight text-bone">{game?.board_size || "—"} 人局大厅</h1>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <StatusBadge tone="gold">等待入座</StatusBadge>
              {game?.is_host && <span className="text-sm text-smoke">你是房主，可以安排 AI 席位。</span>}
            </div>
          </div>
          <button className="btn-ghost w-fit" onClick={() => router.push("/")}>← 返回当前对局</button>
        </div>

        {error && <div role="alert" className="mb-6 rounded-xl border border-cinnabar/30 bg-cinnabar/10 px-4 py-3 text-sm text-[#ef8f87]">{error}</div>}

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
          <Panel className="p-5 sm:p-6" title={<><div className="eyebrow mb-2">SEAT MAP</div><h2 className="font-serif text-2xl font-semibold text-bone">牌桌座位</h2></>}>
            <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {summary?.players.map((player) => {
                const empty = player.controller_type === "empty";
                const isAI = player.controller_type === "ai";
                const cfg = cfgOf(player.seat);
                const footer = game?.is_host && (empty || isAI) ? (
                  <div className="space-y-2">
                    <select
                      className="input px-2.5 py-2 text-xs"
                      aria-label={`${player.seat}号模型`}
                      value={cfg.modelId ?? ""}
                      onChange={(event) => setCfg(player.seat, { modelId: event.target.value ? Number(event.target.value) : null })}
                    >
                      <option value="">默认模型</option>
                      {enabledModels.map((model) => <option key={model.id} value={model.id}>{model.display_name}</option>)}
                    </select>
                    <select
                      className="input px-2.5 py-2 text-xs"
                      aria-label={`${player.seat}号人格`}
                      value={cfg.personaId ?? ""}
                      onChange={(event) => setCfg(player.seat, { personaId: event.target.value ? Number(event.target.value) : null })}
                    >
                      <option value="">自由发挥</option>
                      {personas.map((persona) => <option key={persona.id} value={persona.id}>{persona.name}</option>)}
                    </select>
                    <div className="flex gap-2">
                      {empty && <button className="btn-primary flex-1 px-2.5 py-2 text-xs" disabled={busy} onClick={() => addAI(player.seat)}>＋ 添加 AI</button>}
                      {isAI && (
                        <>
                          <button className="btn-ghost flex-1 px-2.5 py-2 text-xs" disabled={busy} onClick={() => updateAI(player.seat)}>更换</button>
                          <button className="btn-ghost px-2.5 py-2 text-xs text-[#ef8f87]" disabled={busy} onClick={() => act("/game/current/ai-seats", { seat_number: player.seat, action: "remove" })}>移除</button>
                        </>
                      )}
                    </div>
                  </div>
                ) : !empty && player.controller_type === "human" && player.user_id === user.id ? (
                  <div className="flex gap-2">
                    <button className={`btn flex-1 px-2.5 py-2 text-xs ${player.ready ? "btn-primary" : "btn-ghost"}`} disabled={busy} onClick={() => act("/game/current/ready", { ready: !player.ready })}>
                      {player.ready ? "已准备 ✓" : "准备"}
                    </button>
                    <button className="btn-ghost px-2.5 py-2 text-xs" disabled={busy} onClick={() => act("/game/current/leave")}>离开</button>
                  </div>
                ) : undefined;

                return <SeatCard key={player.seat} player={player} variant="lobby" footer={footer} />;
              })}
            </div>
          </Panel>

          <aside className="space-y-4">
            {me === null && (
              <Panel className="p-5 sm:p-6">
                <div className="eyebrow mb-2">YOUR SEAT</div>
                <h2 className="font-serif text-xl font-semibold text-bone">还没有入座</h2>
                <p className="mt-2 text-sm leading-6 text-smoke">加入这场对局，成为牌桌上的一位真人玩家。</p>
                <button className="btn-primary mt-5 w-full" onClick={() => act("/game/current/join")} disabled={busy}>加入游戏</button>
              </Panel>
            )}

            {game?.is_host && (
              <Panel className="p-5 sm:p-6">
                <div className="eyebrow mb-2">HOST CONSOLE</div>
                <h2 className="font-serif text-xl font-semibold text-bone">AI 补齐空位</h2>
                <p className="mt-2 text-sm leading-6 text-smoke">用一套默认配置快速填满剩余席位，也可以回到座位牌单独调整。</p>
                <div className="mt-5 space-y-3">
                  <div>
                    <label className="label" htmlFor="fill-model">默认模型</label>
                    <select id="fill-model" className="input" value={fillModelId ?? ""} onChange={(event) => setFillModelId(event.target.value ? Number(event.target.value) : null)}>
                      <option value="">默认模型</option>
                      {enabledModels.map((model) => <option key={model.id} value={model.id}>{model.display_name}（{model.model_name}）</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="label" htmlFor="fill-persona">默认人格</label>
                    <select id="fill-persona" className="input" value={fillPersonaId ?? ""} onChange={(event) => setFillPersonaId(event.target.value ? Number(event.target.value) : null)}>
                      <option value="">自由发挥</option>
                      {personas.map((persona) => <option key={persona.id} value={persona.id}>{persona.name}</option>)}
                    </select>
                  </div>
                  <button className="btn-ghost w-full" disabled={busy} onClick={() => act("/game/current/ai-fill", { model_config_id: fillModelId, persona_id: fillPersonaId })}>AI 补齐所有空位</button>
                </div>
                {models.length === 0 && <p className="mt-3 text-xs leading-5 text-[#e7bd68]">尚未配置模型，请先在“模型配置”页添加。</p>}
              </Panel>
            )}

            {game?.is_host && (
              <Panel className="border-gold/25 bg-gradient-to-br from-gold/10 to-transparent p-5 sm:p-6">
                <div className="eyebrow mb-2">READY TO BEGIN?</div>
                <h2 className="font-serif text-xl font-semibold text-bone">牌桌准备好了吗？</h2>
                <p className="mt-2 text-sm leading-6 text-smoke">开始后将锁定座位配置并进入第一夜。</p>
                <button className="btn-primary mt-5 w-full py-3" disabled={busy} onClick={() => act("/game/current/start")}>开始游戏</button>
              </Panel>
            )}
          </aside>
        </div>

        {summary?.players.some((player) => player.controller_type === "ai") && (
          <div className="mt-5 text-right text-xs text-smoke/70">
            AI 配置：{summary.players.filter((player) => player.controller_type === "ai").map((player) => `${player.seat}号 ${modelName(player.model_config_id)} · ${personaName(player.persona_name)}`).join(" / ")}
          </div>
        )}
      </main>
    </div>
  );
}
