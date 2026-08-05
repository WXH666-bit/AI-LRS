"use client";

import StatusBadge from "@/components/ui/StatusBadge";
import { roleLabel } from "@/lib/formatEvent";
import type { GameView, LegalAction, LegalTarget } from "@/lib/types";

interface ActionDockProps {
  view: GameView;
  me: GameView["me"];
  myTurn: boolean;
  speech: string;
  onSpeechChange: (value: string) => void;
  chatText: string;
  onChatTextChange: (value: string) => void;
  busy: boolean;
  submit: (action: LegalAction, target?: number) => void;
}

export default function ActionDock({ view, me, myTurn, speech, onSpeechChange, chatText, onChatTextChange, busy, submit }: ActionDockProps) {
  const actions = view.legal_actions || [];
  const targets = view.legal_targets || [];
  const isWolf = me?.role === "wolf";
  const wolfChat = actions.find((action) => action.type === "wolf_chat");

  return (
    <div className="panel-elevated overflow-hidden">
      <div className="border-b border-white/10 bg-gradient-to-br from-gold/10 to-transparent p-5 sm:p-6">
        <div className="eyebrow mb-2">YOUR VERDICT</div>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="font-serif text-2xl font-semibold text-bone">{me ? `我的座位 · ${me.seat}号` : "观战模式"}</h2>
            <p className="mt-2 text-sm text-smoke">{myTurn ? "现在轮到你做出判断。" : "先听完牌桌上的证词。"}</p>
          </div>
          {me?.role && <StatusBadge tone={me.role === "wolf" ? "danger" : "success"}>{roleLabel(me.role)}</StatusBadge>}
        </div>
      </div>

      <div className="space-y-4 p-5 sm:p-6">
        {me && !me.alive && <div className="rounded-xl border border-white/10 bg-white/5 px-3.5 py-3 text-sm text-smoke">你已出局，可以继续观看公开信息。</div>}
        {me?.controller_type === "trustee" && <div className="rounded-xl border border-gold/25 bg-gold/5 px-3.5 py-3 text-sm leading-6 text-[#e7bd68]">当前为 AI 托管（连续超时），下一轮行动可夺回控制权。</div>}

        {me?.role === "seer" && view.private?.checks?.length > 0 && (
          <div className="rounded-xl border border-sage/20 bg-sage/5 p-3 text-xs text-[#9bd3c6]">
            <div className="mb-2 font-semibold">查验记录</div>
            <div className="space-y-1">{view.private.checks.map((check: any, index: number) => <div key={index}>第 {check.night} 夜 · {check.target}号：{check.result === "wolf" ? "狼人" : "好人"}</div>)}</div>
          </div>
        )}
        {me?.role === "witch" && <div className="rounded-xl border border-white/10 bg-ink-900/80 p-3 text-xs text-smoke"><div>解药：{view.private.save_used ? "已用" : "未用"}</div><div className="mt-1">毒药：{view.private.poison_used ? "已用" : "未用"}</div></div>}
        {me?.role === "guard" && view.private.last_target && <div className="rounded-xl border border-white/10 bg-ink-900/80 p-3 text-xs leading-5 text-smoke">上一晚守护：{view.private.last_target}号（今晚不能重复守护）</div>}

        {actions.length === 0 && <div className="rounded-xl border border-dashed border-white/10 px-4 py-8 text-center text-sm text-smoke">{myTurn ? "轮到你了，等待操作加载…" : "等待其他玩家…"}</div>}

        {actions.length > 0 && (
          <div className="space-y-5">
            {actions.map((action) => (
              <div key={`${action.type}-${action.action}-${action.skill}`} className="border-t border-white/10 pt-4 first:border-t-0 first:pt-0">
                {action.type === "speak" && (
                  <div className="space-y-2.5">
                    <div className="text-xs font-semibold text-smoke">轮到你发言</div>
                    <textarea className="input min-h-[120px] resize-y" placeholder="写下你的判断、怀疑和理由…" value={speech} onChange={(event) => onSpeechChange(event.target.value)} maxLength={1000} />
                    <div className="flex gap-2"><button className="btn-primary flex-1" disabled={busy || !speech.trim()} onClick={() => submit(action)}>发送发言</button><button className="btn-ghost" disabled={busy} onClick={() => submit({ ...action, type: "pass" })}>跳过</button></div>
                  </div>
                )}

                {action.type === "vote" && (
                  <div><div className="mb-2 text-xs font-semibold text-smoke">{action.label}</div><div className="grid grid-cols-2 gap-2 sm:grid-cols-3">{targets.map((target: LegalTarget) => <button key={`${action.type}-${target.seat}`} className="btn-ghost px-3 py-2 text-xs" disabled={busy} onClick={() => submit(action, target.seat)}>{target.label}</button>)}<button className="btn-subtle px-3 py-2 text-xs" disabled={busy} onClick={() => submit(action, 0)}>弃权</button></div></div>
                )}

                {action.type === "use_skill" && (
                  <div><div className="mb-2 text-xs font-semibold text-smoke">{action.label}</div><div className="flex flex-wrap gap-2">{targets.filter((target) => !target.kind || target.kind === action.skill?.replace("witch_", "")).map((target: LegalTarget) => <button key={`${action.skill}-${target.seat}`} className="btn-ghost px-3 py-2 text-xs" disabled={busy} onClick={() => submit(action, target.seat)}>{target.kind === "save" ? `💊 救 ${target.seat}号` : target.kind === "poison" ? `☠️ 毒 ${target.seat}号` : target.label}</button>)}<button className="btn-subtle px-3 py-2 text-xs" disabled={busy} onClick={() => submit(action)}>不使用</button></div></div>
                )}

                {action.type === "sheriff_action" && action.action !== "transfer" && <button className={`${action.action === "apply" ? "btn-primary" : "btn-ghost"} w-full`} disabled={busy} onClick={() => submit(action)}>{action.label}</button>}

                {action.type === "sheriff_action" && action.action === "transfer" && <div><div className="mb-2 text-xs font-semibold text-smoke">移交警徽给：</div><div className="flex flex-wrap gap-2">{targets.map((target: LegalTarget) => <button key={target.seat} className="btn-ghost px-3 py-2 text-xs" disabled={busy} onClick={() => submit(action, target.seat)}>{target.label}</button>)}</div><button className="btn-subtle mt-2 w-full text-xs text-[#ef8f87]" disabled={busy} onClick={() => submit({ ...action, action: "destroy" })}>撕毁警徽</button></div>}

                {action.type === "wolf_explode" && <button className="btn-danger w-full" disabled={busy} onClick={() => submit(action)}>💥 {action.label}</button>}
                {action.type === "wolf_chat" && <div className="space-y-2.5"><div className="text-xs font-semibold text-[#c9b6e4]">狼队私聊</div><input className="input" placeholder="给狼队友的私聊消息…" value={chatText} onChange={(event) => onChatTextChange(event.target.value)} maxLength={500} /><button className="btn-ghost w-full text-[#c9b6e4]" disabled={busy || !chatText.trim()} onClick={() => submit(action)}>发送到狼队频道</button></div>}
                {action.type === "pass" && action.label !== "跳过" && action.label !== "弃权" && action.label !== "不使用" && <button className="btn-subtle w-full text-smoke" disabled={busy} onClick={() => submit(action)}>{action.label}</button>}
              </div>
            ))}
          </div>
        )}

        {isWolf && !wolfChat && me?.alive && <div className="text-[10px] leading-5 text-smoke/60">狼人私聊仅在夜间窗口开启时可用。</div>}
      </div>
    </div>
  );
}
