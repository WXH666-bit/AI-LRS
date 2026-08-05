"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Header from "@/components/Header";
import { api } from "@/lib/api";
import { formatEvent, roleLabel, type DisplayLine } from "@/lib/formatEvent";
import type { GameView, LegalAction, LegalTarget } from "@/lib/types";
import { useUser } from "@/lib/useUser";
import { GameClient } from "@/lib/ws";

const KIND_COLORS: Record<string, string> = {
  phase: "text-amber-400 font-bold text-center",
  public: "text-moon",
  wolf: "text-purple-300",
  private: "text-emerald-300",
  death: "text-red-400",
  system: "text-sky-300",
  me: "text-amber-300",
};

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
  const [now, setNow] = useState(Date.now());
  const [busy, setBusy] = useState(false);
  const clientRef = useRef<GameClient | null>(null);
  const logRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!user) return;
    const client = new GameClient({
      onEvents: (evs) =>
        setEvents((prev) => {
          const known = new Set(prev.map((e) => e.seq));
          const fresh = evs
            .map((e) => formatEvent(e))
            .filter((l): l is DisplayLine => l !== null && !known.has(l.seq));
          // 相邻重复的阶段行（每个行动窗口都会发 phase_change）只保留一条，
          // 需跨批次比较（prev 的最后一条与 fresh 的第一条）
          const deduped: DisplayLine[] = [];
          for (const l of fresh) {
            const last = deduped.length ? deduped[deduped.length - 1] : prev[prev.length - 1];
            if (!(l.kind === "phase" && last?.kind === "phase" && last?.text === l.text)) {
              deduped.push(l);
            }
          }
          return [...prev, ...deduped];
        }),
      onView: (v) => setView(v),
      onError: (msg) => {
        setToast(msg);
        setTimeout(() => setToast(""), 3500);
        // 连接被拒绝（对局已结束/不存在）→ 回首页确认状态
        api<{ game: { status: string } | null }>("/game/current")
          .then((d) => {
            if (!d.game || d.game.status === "ended" || d.game.status === "lobby") {
              router.replace("/");
            }
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
  }, [user]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [events.length]);

  const wolfEvents = useMemo(() => events.filter((e) => e.kind === "wolf"), [events]);
  const publicEvents = useMemo(() => events.filter((e) => e.kind !== "wolf"), [events]);

  if (loading || !user) return <div className="min-h-screen" />;

  if (!view) {
    return (
      <div className="min-h-screen">
        <Header user={user} />
        <div className="flex items-center justify-center h-[60vh] text-slate-400">
          {connected ? "对局加载中…" : "正在连接对局服务…"}
        </div>
      </div>
    );
  }

  const g = view.game;
  const me = view.me;
  const isEnded = g.status === "ended";
  const myTurn = me !== null && me.alive && g.acting_seats.includes(me.seat);
  const deadline = Math.max(0, Math.ceil(g.deadline));
  const isWolf = me?.role === "wolf";
  const canControl = g.is_all_ai && view.game.status !== "ended";

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
      if (action.action === "transfer") {
        send("sheriff_action", { action: "transfer", target });
      } else {
        send("sheriff_action", { action: action.action });
      }
    } else if (action.type === "pass") {
      send("pass", {});
    }
    setTimeout(() => setBusy(false), 200);
  }

  return (
    <div className="min-h-screen">
      <Header user={user} />
      {toast && (
        <div className="fixed top-16 left-1/2 -translate-x-1/2 z-50 bg-red-900/90 text-red-100 px-4 py-2 rounded-lg text-sm shadow-lg">
          {toast}
        </div>
      )}

      {/* 顶栏 */}
      <div className="border-b border-night-600/60 bg-night-900/80 sticky top-[57px] z-10">
        <div className="max-w-7xl mx-auto px-4 py-2.5 flex flex-wrap items-center gap-x-6 gap-y-1">
          <span className="font-bold text-amber-300">{g.phase_label}</span>
          {g.window_kind && <span className="text-sm text-slate-300">🎯 {g.window_label}</span>}
          <span className="text-sm text-slate-400">
            {g.phase === "night" ? `第 ${g.night} 夜` : `第 ${g.day} 天`}
          </span>
          {myTurn && (
            <span className="text-sm font-bold text-amber-300">
              ⏱ {deadline}s
            </span>
          )}
          {!myTurn && deadline > 0 && g.acting_seats.length > 0 && (
            <span className="text-sm text-slate-500">⏱ {deadline}s</span>
          )}
          {g.acting_seats.length > 0 && (
            <span className="text-sm">
              等待：
              {g.acting_seats.map((s) => (
                <span key={s} className="text-slate-300 mx-0.5">
                  {s}号
                </span>
              ))}
              {me && myTurn ? "（你！）" : ""}
            </span>
          )}
          <span className={`ml-auto text-xs ${connected ? "text-emerald-400" : "text-red-400"}`}>
            {connected ? "● 已连接" : "○ 连接中断，重连中…"}
          </span>
          {canControl && (
            <div className="flex items-center gap-1.5">
              {g.status === "paused" ? (
                <button className="btn-primary text-xs px-3 py-1" onClick={() => api("/game/current/resume", { method: "POST" })}>
                  继续
                </button>
              ) : (
                <button className="btn-ghost text-xs px-3 py-1" onClick={() => api("/game/current/pause", { method: "POST" })}>
                  暂停
                </button>
              )}
              {[1, 2, 3].map((s) => (
                <button
                  key={s}
                  className={`text-xs px-2.5 py-1 rounded ${g.speed === s ? "bg-amber-500 text-night-950" : "bg-night-700 hover:bg-night-600"}`}
                  onClick={() => api("/game/current/speed", { method: "POST", body: JSON.stringify({ speed: s }) })}
                >
                  {s === 1 ? "1x" : s === 2 ? "2x" : "快进"}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <main className="max-w-7xl mx-auto px-4 py-5 grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-5">
        <div className="space-y-5">
          {/* 座位区 */}
          <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-2.5">
            {view.players.map((p) => {
              const acting = g.acting_seats.includes(p.seat);
              const isMe = me?.seat === p.seat;
              const revealed = view.roles_revealed?.[p.seat];
              const role = revealed ? roleLabel(revealed) : p.role ? roleLabel(p.role) : "";
              return (
                <div
                  key={p.seat}
                  className={`card p-3 text-center relative ${!p.alive ? "opacity-45" : ""} ${
                    acting ? "acting-glow ring-1 ring-amber-400" : ""
                  } ${isMe ? "ring-1 ring-emerald-400" : ""}`}
                >
                  <div className="text-[10px] text-slate-500">{p.seat}号</div>
                  <div className="text-sm font-medium truncate mt-0.5">
                    {!p.alive && "💀 "}
                    {p.name}
                    {isMe && "（我）"}
                  </div>
                  <div className="text-[10px] mt-1">
                    {g.sheriff_seat === p.seat && <span className="text-amber-400 mr-1">🎖️警长</span>}
                    <span className={p.alive ? "text-emerald-400" : "text-red-400"}>
                      {p.alive ? "存活" : "出局"}
                    </span>
                  </div>
                  {role && <div className="text-[10px] text-purple-300 mt-0.5">{role}</div>}
                  {acting && <div className="text-[10px] text-amber-300 mt-0.5 animate-pulse">行动中</div>}
                </div>
              );
            })}
          </div>

          {/* 事件流 */}
          <div className="card flex flex-col h-[440px]">
            <div className="flex items-center gap-1 px-4 pt-2 border-b border-night-700">
              <button
                className={`px-3 py-2 text-sm rounded-t ${tab === "public" ? "text-amber-300 border-b-2 border-amber-400" : "text-slate-400"}`}
                onClick={() => setTab("public")}
              >
                公开频道 {isWolf && `(${publicEvents.length})`}
              </button>
              {isWolf && (
                <button
                  className={`px-3 py-2 text-sm rounded-t ${tab === "wolf" ? "text-purple-300 border-b-2 border-purple-400" : "text-slate-400"}`}
                  onClick={() => setTab("wolf")}
                >
                  🐺 狼队频道 {wolfEvents.length > 0 && `(${wolfEvents.length})`}
                </button>
              )}
            </div>
            <div ref={logRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-1.5 text-sm">
              {(tab === "wolf" ? wolfEvents : publicEvents).map((e) => (
                <div key={e.seq} className={KIND_COLORS[e.kind] || "text-moon"}>
                  {e.text}
                </div>
              ))}
              {(tab === "wolf" ? wolfEvents : publicEvents).length === 0 && (
                <div className="text-slate-500 text-center mt-8">暂无消息</div>
              )}
            </div>
          </div>
        </div>

        {/* 右侧面板 */}
        <div className="space-y-4">
          {isEnded ? (
            <div className="card p-6 text-center">
              <div className="text-2xl mb-2">
                {g.winner === "good" ? "🏆 好人阵营获胜" : "🐺 狼人阵营获胜"}
              </div>
              <p className="text-sm text-slate-400 mb-4">{g.end_reason}</p>
              <div className="grid grid-cols-2 gap-2 text-sm mb-4">
                {view.players.map((p) => (
                  <div key={p.seat} className="bg-night-900 rounded px-2 py-1.5 flex justify-between">
                    <span className="truncate">{p.seat}号 {p.name}</span>
                    <span>{view.roles_revealed?.[p.seat] ? roleLabel(view.roles_revealed[p.seat]) : "—"}</span>
                  </div>
                ))}
              </div>
              <button className="btn-ghost w-full mb-2" onClick={() => router.push(`/history/${g.game_id}`)}>
                查看完整回放
              </button>
              <button className="btn-primary w-full" onClick={() => router.push("/")}>
                返回首页
              </button>
            </div>
          ) : (
            <ActionPanel
              view={view}
              me={me}
              myTurn={myTurn}
              speech={speech}
              setSpeech={setSpeech}
              chatText={chatText}
              setChatText={setChatText}
              busy={busy}
              submit={submitAction}
            />
          )}
        </div>
      </main>
    </div>
  );
}

function ActionPanel(props: {
  view: GameView;
  me: GameView["me"];
  myTurn: boolean;
  speech: string;
  setSpeech: (s: string) => void;
  chatText: string;
  setChatText: (s: string) => void;
  busy: boolean;
  submit: (a: LegalAction, target?: number) => void;
}) {
  const { view, me, myTurn, speech, setSpeech, chatText, setChatText, busy, submit } = props;
  const g = view.game;
  const actions = view.legal_actions || [];
  const targets = view.legal_targets || [];
  const isWolf = me?.role === "wolf";
  const wolfChat = actions.find((a) => a.type === "wolf_chat");

  return (
    <div className="card p-5 space-y-4">
      <div>
        <div className="flex items-center justify-between mb-1">
          <h2 className="font-bold">{me ? `我的座位 · ${me.seat}号` : "观战模式"}</h2>
          {me && me.role && <span className="text-sm text-purple-300">身份：{roleLabel(me.role)}</span>}
        </div>
        {me && !me.alive && <p className="text-xs text-red-400">你已出局，可继续观看公开信息</p>}
        {me?.controller_type === "trustee" && (
          <p className="text-xs text-amber-400">当前为 AI 托管（连续超时），下一轮行动可夺回控制权</p>
        )}
      </div>

      {/* 女巫/预言家/守卫 私有信息 */}
      {me?.role === "seer" && (view.private?.checks?.length > 0) && (
        <div className="text-xs bg-night-900 rounded p-3 space-y-1">
          <div className="text-slate-400">查验记录：</div>
          {view.private.checks.map((c: any, i: number) => (
            <div key={i} className={c.result === "wolf" ? "text-red-300" : "text-emerald-300"}>
              第{c.night}夜查 {c.target}号：{c.result === "wolf" ? "狼人" : "好人"}
            </div>
          ))}
        </div>
      )}
      {me?.role === "witch" && (
        <div className="text-xs bg-night-900 rounded p-3 space-y-1 text-slate-300">
          <div>解药：{view.private.save_used ? "已用" : "未用"}</div>
          <div>毒药：{view.private.poison_used ? "已用" : "未用"}</div>
        </div>
      )}
      {me?.role === "guard" && view.private.last_target && (
        <div className="text-xs bg-night-900 rounded p-3 text-slate-300">
          上一晚守护：{view.private.last_target}号（今晚不能重复守护）
        </div>
      )}

      {actions.length === 0 && (
        <div className="text-sm text-slate-500 text-center py-4">
          {myTurn ? "轮到你了" : "等待其他玩家…"}
        </div>
      )}

      {actions.length > 0 && (
        <div className="space-y-3">
          {actions.map((a) => (
            <div key={`${a.type}-${a.action}-${a.skill}`}>
              {/* 发言/遗言 */}
              {a.type === "speak" && (
                <div className="space-y-2">
                  <textarea
                    className="input min-h-[90px]"
                    placeholder="输入你的发言…"
                    value={speech}
                    onChange={(e) => setSpeech(e.target.value)}
                    maxLength={1000}
                  />
                  <div className="flex gap-2">
                    <button className="btn-primary flex-1" disabled={busy || !speech.trim()} onClick={() => submit(a)}>
                      发送发言
                    </button>
                    <button className="btn-ghost" disabled={busy} onClick={() => submit({ ...a, type: "pass" })}>
                      跳过
                    </button>
                  </div>
                </div>
              )}

              {/* 投票 */}
              {a.type === "vote" && (
                <div>
                  <div className="text-xs text-slate-400 mb-1.5">{a.label}</div>
                  <div className="flex flex-wrap gap-1.5">
                    {targets.map((t: LegalTarget) => (
                      <button
                        key={`${a.type}-${t.seat}`}
                        className="btn-ghost text-xs px-3 py-1.5"
                        disabled={busy}
                        onClick={() => submit(a, t.seat)}
                      >
                        {t.label}
                      </button>
                    ))}
                    <button className="btn-ghost text-xs px-3 py-1.5 text-slate-400" disabled={busy} onClick={() => submit(a, 0)}>
                      弃权
                    </button>
                  </div>
                </div>
              )}

              {/* 技能 */}
              {a.type === "use_skill" && (
                <div>
                  <div className="text-xs text-slate-400 mb-1.5">{a.label}</div>
                  <div className="flex flex-wrap gap-1.5">
                    {targets
                      .filter((t) => !t.kind || t.kind === a.skill?.replace("witch_", "") || a.skill === "witch_poison")
                      .map((t: LegalTarget) => (
                        <button
                          key={`${a.skill}-${t.seat}`}
                          className="btn-ghost text-xs px-3 py-1.5"
                          disabled={busy}
                          onClick={() => submit(a, t.seat)}
                        >
                          {t.kind === "save" ? `💊 救 ${t.seat}号` : t.kind === "poison" ? `☠️ 毒 ${t.seat}号` : t.label}
                        </button>
                      ))}
                    <button className="btn-ghost text-xs px-3 py-1.5 text-slate-400" disabled={busy} onClick={() => submit(a, undefined)}>
                      不使用
                    </button>
                  </div>
                </div>
              )}

              {/* 上警 */}
              {a.type === "sheriff_action" && a.action !== "transfer" && (
                <button
                  className={`${a.action === "apply" ? "btn-primary" : a.action === "withdraw" ? "btn-ghost" : "btn-ghost"} w-full`}
                  disabled={busy}
                  onClick={() => submit(a)}
                >
                  {a.label}
                </button>
              )}

              {/* 警徽移交 */}
              {a.type === "sheriff_action" && a.action === "transfer" && (
                <div>
                  <div className="text-xs text-slate-400 mb-1.5">移交警徽给：</div>
                  <div className="flex flex-wrap gap-1.5">
                    {targets.map((t: LegalTarget) => (
                      <button key={t.seat} className="btn-ghost text-xs px-3 py-1.5" disabled={busy} onClick={() => submit(a, t.seat)}>
                        {t.label}
                      </button>
                    ))}
                  </div>
                  <button className="btn-ghost w-full mt-2 text-red-300 text-xs" disabled={busy} onClick={() => submit({ ...a, action: "destroy" })}>
                    撕毁警徽
                  </button>
                </div>
              )}

              {/* 自爆 / 狼人私聊 / 弃权 */}
              {a.type === "wolf_explode" && (
                <button className="btn-danger w-full" disabled={busy} onClick={() => submit(a)}>
                  💥 {a.label}
                </button>
              )}
              {a.type === "wolf_chat" && (
                <div className="space-y-2">
                  <input
                    className="input"
                    placeholder="给狼队友的私聊消息…"
                    value={chatText}
                    onChange={(e) => setChatText(e.target.value)}
                    maxLength={500}
                  />
                  <button className="btn-ghost w-full text-purple-300" disabled={busy || !chatText.trim()} onClick={() => submit(a)}>
                    发送到狼队频道
                  </button>
                </div>
              )}
              {a.type === "pass" && a.label !== "跳过" && a.label !== "弃权" && a.label !== "不使用" && (
                <button className="btn-ghost w-full text-slate-400" disabled={busy} onClick={() => submit(a)}>
                  {a.label}
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {isWolf && !wolfChat && me?.alive && (
        <div className="text-[10px] text-slate-500">（狼人私聊仅在夜间窗口开启时可用）</div>
      )}
    </div>
  );
}
