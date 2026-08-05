import type { ReactNode } from "react";
import { roleLabel } from "@/lib/formatEvent";
import type { PlayerInfo } from "@/lib/types";
import StatusBadge from "@/components/ui/StatusBadge";

export interface SeatCardProps {
  player: PlayerInfo;
  variant: "lobby" | "game";
  acting?: boolean;
  isMe?: boolean;
  revealedRole?: string;
  sheriff?: boolean;
  footer?: ReactNode;
}

export default function SeatCard({ player, variant, acting = false, isMe = false, revealedRole, sheriff = false, footer }: SeatCardProps) {
  const empty = player.controller_type === "empty";
  const role = revealedRole || (variant === "game" ? player.role : null);
  const tone = empty ? "muted" : player.alive ? "success" : "muted";

  return (
    <article
      className={`relative overflow-hidden rounded-[18px] border p-4 transition-all ${
        empty ? "border-dashed border-white/15 bg-ink-900/40" : "border-white/10 bg-ink-800/80"
      } ${!player.alive ? "opacity-55" : ""} ${acting ? "acting-glow border-gold/70" : ""} ${isMe ? "border-sage/60" : ""}`}
    >
      {acting && <div className="absolute inset-x-0 top-0 h-0.5 bg-gold" />}
      <div className="flex items-start justify-between gap-2">
        <span className="font-mono text-[10px] font-semibold tracking-[0.16em] text-gold">{String(player.seat).padStart(2, "0")}</span>
        {!empty && <StatusBadge tone={tone} className="px-1.5 py-0.5 text-[9px]">{player.alive ? "存活" : "出局"}</StatusBadge>}
      </div>

      {empty ? (
        <div className="mt-6">
          <div className="text-sm font-medium text-smoke">空位</div>
          <div className="mt-1 text-xs text-smoke/60">等待一位玩家或 AI</div>
        </div>
      ) : (
        <>
          <div className="mt-5 flex items-center gap-2">
            <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border text-sm font-semibold ${isMe ? "border-sage/40 bg-sage/10 text-sage" : "border-white/10 bg-ink-900 text-gold"}`}>
              {player.name.slice(0, 1)}
            </div>
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-bone">{player.name}</div>
              <div className="mt-1 text-[10px] text-smoke">
                {player.controller_type === "human" ? "真人玩家" : player.controller_type === "trustee" ? "AI 托管" : "AI 玩家"}
              </div>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-1.5">
            {player.is_host && <span className="rounded-full border border-gold/20 bg-gold/10 px-2 py-0.5 text-[10px] text-[#e7bd68]">房主</span>}
            {sheriff && <span className="rounded-full border border-gold/20 bg-gold/10 px-2 py-0.5 text-[10px] text-[#e7bd68]">警长</span>}
            {isMe && <span className="rounded-full border border-sage/25 bg-sage/10 px-2 py-0.5 text-[10px] text-[#9bd3c6]">这是你</span>}
            {acting && <span className="rounded-full border border-gold/25 bg-gold/10 px-2 py-0.5 text-[10px] font-semibold text-[#e7bd68]">行动中</span>}
            {role && <span className={`rounded-full border px-2 py-0.5 text-[10px] ${role === "wolf" ? "border-cinnabar/30 bg-cinnabar/10 text-[#ef8f87]" : "border-sage/25 bg-sage/10 text-[#9bd3c6]"}`}>{roleLabel(role)}</span>}
          </div>
        </>
      )}

      {footer && <div className="mt-4 border-t border-white/10 pt-3">{footer}</div>}
    </article>
  );
}
