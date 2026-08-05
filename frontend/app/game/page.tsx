"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Header from "@/components/Header";
import ActionDock from "@/components/game/ActionDock";
import EventEntry from "@/components/game/EventEntry";
import PhaseRibbon from "@/components/game/PhaseRibbon";
import RoleRoster from "@/components/game/RoleRoster";
import SeatCard from "@/components/game/SeatCard";
import Panel from "@/components/ui/Panel";
import StatusBadge from "@/components/ui/StatusBadge";
import { api } from "@/lib/api";
import { formatEvent, roleLabel, type DisplayLine } from "@/lib/formatEvent";
import type { GameView, LegalAction } from "@/lib/types";
import { useUser } from "@/lib/useUser";
import { GameClient } from "@/lib/ws";

export default function GamePage() {
  const { user, loading } = useUser();
  const router = useRouter();
  const [view, setView] = useState<GameView | null>(null);
  const [events, setEvents] = useState<DisplayLine[]>([]);
  const [connected, setConnected] = useState(false);
  const [toast, setToast] = useState("");
  const [speech, setSpeech] = useState("");
  const [chatText, setChatText] = useState("");
  const [tab, setTab] = useState<"public" | "wolf">("public");
  const [, setNow] = useState(Date.now());
  const [busy, setBusy] = useState(false);
  const clientRef = useRef<GameClient | null>(null);
  const logRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!user) return;
    const client = new GameClient({
      onEvents: (incoming) => setEvents((previous) => {
        const known = new Set(previous.map((event) => event.seq));
        const fresh = incoming
          .map((event) => formatEvent(event))
          .filter((line): line is DisplayLine => line !== null && !known.has(line.seq));
        const deduped: DisplayLine[] = [];
        for (const line of fresh) {
          const last = deduped.length ? deduped[deduped.length - 1] : previous[previous.length - 1];
          if (!(line.kind === "phase" && last?.kind === "phase" && last.text === line.text)) deduped.push(line);
        }
        return [...previous, ...deduped];
      }),
      onView: (nextView) => setView(nextView),
      onError: (message) => {
        setToast(message);
        setTimeout(() => setToast(""), 3500);
        api<{ game: { status: string } | null }>("/game/current")
          .then((data) => {
            if (!data.game || data.game.status === "ended" || data.game.status === "lobby") router.replace("/");
          })
          .catch(() => {});
      },
      onStatus: setConnected,
    });
    clientRef.current = client;
    void client.connect();
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => {
      clearInterval(tick);
      client.close();
    };
  }, [user, router]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [events.length]);

  const wolfEvents = useMemo(() => events.filter((event) => event.kind === "wolf"), [events]);
  const publicEvents = useMemo(() => events.filter((event) => event.kind !== "wolf"), [events]);

  if (loading || !user) return <div className="min-h-screen" />;

  if (!view) {
    return (
      <div className="min-h-screen">
        <Header user={user} />
        <main className="mx-auto flex min-h-[60vh] max-w-7xl items-center justify-center px-4 sm:px-6">
          <div className="text-center"><div className="eyebrow mb-3">CONNECTING TO THE TABLE</div><h1 className="font-serif text-3xl font-semibold text-bone">{connected ? "正在加载对局…" : "正在连接对局服务…"}</h1><p className="mt-3 text-sm text-smoke">牌桌状态会在连接建立后出现。</p></div>
        </main>
      </div>
    );
  }

  const game = view.game;
  const me = view.me;
  const isEnded = game.status === "ended";
  const myTurn = me !== null && me.alive && game.acting_seats.includes(me.seat);
  const deadline = Math.max(0, Math.ceil(game.deadline));
  const canControl = game.is_all_ai && !isEnded;

  function send(type: string, payload?: Record<string, any>) {
    clientRef.current?.sendCommand(type, payload);
  }

  function submitAction(action: LegalAction, target?: number) {
    setBusy(true);
    if (action.type === "speak") {
      send("speak", { text: speech });
      setSpeech("");
    } else if (action.type === "vote") {
      send("vote", { target: target ?? 0 });
    } else if (action.type === "use_skill") {
      send("use_skill", { skill: action.skill, target: target ?? null });
    } else if (action.type === "wolf_explode") {
      if (confirm("确定自爆吗？自爆后立即结束白天进入夜晚。")) send("wolf_explode", {});
    } else if (action.type === "wolf_chat") {
      if (chatText.trim()) {
        send("wolf_chat", { text: chatText });
        setChatText("");
      }
    } else if (action.type === "sheriff_action") {
      send("sheriff_action", action.action === "transfer" ? { action: "transfer", target } : { action: action.action });
    } else if (action.type === "pass") {
      send("pass", {});
    }
    setTimeout(() => setBusy(false), 200);
  }

  async function control(path: string, body?: Record<string, unknown>) {
    try {
      await api(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
    } catch (err: any) {
      setToast(err.message || "操作失败");
      setTimeout(() => setToast(""), 3500);
    }
  }

  async function forceEnd() {
    if (!confirm("确定强制结束当前对局？身份将立即揭晓。")) return;
    await control("/game/current/force-end");
  }

  const currentEvents = tab === "wolf" ? wolfEvents : publicEvents;

  return (
    <div className="min-h-screen">
      <Header user={user} />
      {toast && <div role="alert" className="fixed left-1/2 top-24 z-50 -translate-x-1/2 rounded-xl border border-cinnabar/30 bg-ink-800 px-4 py-3 text-sm text-[#ef8f87] shadow-[0_18px_50px_rgb(0_0_0_/_30%)]">{toast}</div>}

      <PhaseRibbon
        game={game}
        connected={connected}
        myTurn={myTurn}
        deadline={deadline}
        onForceEnd={user.role === "admin" && !isEnded ? forceEnd : undefined}
        onPause={canControl ? () => void control("/game/current/pause") : undefined}
        onResume={canControl ? () => void control("/game/current/resume") : undefined}
        onSpeedChange={canControl ? (speed) => void control("/game/current/speed", { speed }) : undefined}
      />

      <main className="mx-auto grid max-w-7xl gap-6 px-4 py-6 sm:px-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="min-w-0 space-y-6">
          <RoleRoster items={game.role_setup} revealed={user.role === "admin" && me === null} />
          <Panel className="p-4 sm:p-5" title={<><div className="eyebrow mb-2">THE PLAYERS</div><h2 className="font-serif text-xl font-semibold text-bone">审判座位</h2></>}>
            <div className="mt-1 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
              {view.players.map((player) => <SeatCard key={player.seat} player={player} variant="game" acting={game.acting_seats.includes(player.seat)} isMe={me?.seat === player.seat} revealedRole={view.roles_revealed?.[player.seat]} sheriff={game.sheriff_seat === player.seat} />)}
            </div>
          </Panel>

          <Panel className="flex min-h-[560px] flex-col overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-4 pt-3 sm:px-6">
              <div className="flex items-center gap-1">
                <button className={`focus-ring rounded-t-xl px-3 py-3 text-sm font-semibold transition-colors ${tab === "public" ? "border-b-2 border-gold text-bone" : "text-smoke hover:text-bone"}`} onClick={() => setTab("public")}>公开频道 <span className="ml-1 text-xs text-smoke">{publicEvents.length}</span></button>
                {me?.role === "wolf" && <button className={`focus-ring rounded-t-xl px-3 py-3 text-sm font-semibold transition-colors ${tab === "wolf" ? "border-b-2 border-[#9b78c5] text-[#c9b6e4]" : "text-smoke hover:text-bone"}`} onClick={() => setTab("wolf")}>狼队频道 <span className="ml-1 text-xs text-smoke">{wolfEvents.length}</span></button>}
              </div>
              <span className="hidden text-xs text-smoke sm:inline">证词会按时间顺序出现</span>
            </div>
            <div ref={logRef} className="flex-1 space-y-2 overflow-y-auto p-4 sm:p-6">
              {currentEvents.map((event, index) => <EventEntry key={event.seq} event={event} isLatest={index === currentEvents.length - 1} />)}
              {currentEvents.length === 0 && <div className="flex min-h-[360px] items-center justify-center text-sm text-smoke">这一条频道暂时没有消息。</div>}
            </div>
          </Panel>
        </div>

        <aside className="min-w-0">
          {isEnded ? (
            <Panel className="overflow-hidden">
              <div className="border-b border-white/10 bg-gradient-to-br from-gold/10 to-transparent p-6 text-center">
                <div className="eyebrow mb-3">CASE CLOSED</div>
                <h2 className="font-serif text-3xl font-semibold text-bone">{game.winner === "good" ? "好人阵营获胜" : game.winner === "wolf" ? "狼人阵营获胜" : "对局已结束"}</h2>
                <p className="mt-3 text-sm text-smoke">{game.end_reason}</p>
              </div>
              <div className="space-y-2 p-5">
                {view.players.map((player) => <div key={player.seat} className="flex items-center justify-between rounded-xl border border-white/10 bg-ink-900/70 px-3 py-2.5 text-sm"><span className="truncate text-bone">{player.seat}号 {player.name}</span><span className={view.roles_revealed?.[player.seat] === "wolf" ? "text-[#ef8f87]" : "text-[#9bd3c6]"}>{view.roles_revealed?.[player.seat] ? roleLabel(view.roles_revealed[player.seat]) : "—"}</span></div>)}
                <button className="btn-ghost mt-3 w-full" onClick={() => router.push(`/history/${game.game_id}`)}>查看完整回放</button>
                <button className="btn-primary w-full" onClick={() => router.push("/")}>返回首页</button>
              </div>
            </Panel>
          ) : (
            <ActionDock view={view} me={me} myTurn={myTurn} speech={speech} onSpeechChange={setSpeech} chatText={chatText} onChatTextChange={setChatText} busy={busy} submit={submitAction} />
          )}
        </aside>
      </main>
    </div>
  );
}
