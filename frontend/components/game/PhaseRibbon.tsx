import StatusBadge from "@/components/ui/StatusBadge";
import type { GameView } from "@/lib/types";

interface PhaseRibbonProps {
  game: GameView["game"];
  connected: boolean;
  myTurn: boolean;
  deadline: number;
  onPause?: () => void;
  onResume?: () => void;
  onSpeedChange?: (speed: number) => void;
  onForceEnd?: () => void;
}

export default function PhaseRibbon({ game, connected, myTurn, deadline, onPause, onResume, onSpeedChange, onForceEnd }: PhaseRibbonProps) {
  const dayLabel = game.phase === "night" ? `第 ${game.night} 夜` : `第 ${game.day} 天`;
  const isDangerPhase = game.phase === "night" || game.phase === "lynch_vote" || game.phase === "lynch_pk_vote";

  return (
    <div className="sticky top-[68px] z-30 border-b border-white/10 bg-ink-950/90 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2">
          <div>
            <div className="eyebrow mb-1">{dayLabel}</div>
            <div className="font-serif text-lg font-semibold text-bone">{game.phase_label}</div>
          </div>
          {game.window_kind && <StatusBadge tone={isDangerPhase ? "danger" : "gold"}>{game.window_label}</StatusBadge>}
          {game.acting_seats.length > 0 && (
            <div className="text-xs text-smoke">
              行动席位：{game.acting_seats.map((seat) => <span key={seat} className="ml-1 font-semibold text-bone">{seat}号</span>)}
              {myTurn && <span className="ml-2 text-gold">（轮到你）</span>}
            </div>
          )}
          {deadline > 0 && <StatusBadge tone={myTurn ? "gold" : "muted"}>⏱ {deadline}s</StatusBadge>}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge tone={connected ? "success" : "danger"}>{connected ? "已连接" : "重连中"}</StatusBadge>
          {onForceEnd && game.status !== "ended" && <button className="btn-danger px-3 py-2 text-xs" onClick={onForceEnd}>强制结束</button>}
          {onPause && onResume && (
            <div className="flex items-center gap-1 rounded-xl border border-white/10 bg-ink-800/80 p-1">
              {game.status === "paused" ? (
                <button className="btn-primary px-3 py-1.5 text-xs" onClick={onResume}>继续</button>
              ) : (
                <button className="btn-ghost px-3 py-1.5 text-xs" onClick={onPause}>暂停</button>
              )}
              {onSpeedChange && [1, 2, 3].map((speed) => (
                <button key={speed} className={`btn px-2.5 py-1.5 text-xs ${game.speed === speed ? "bg-gold text-ink-950" : "bg-transparent text-smoke hover:bg-white/5 hover:text-bone"}`} onClick={() => onSpeedChange(speed)}>
                  {speed === 1 ? "1x" : speed === 2 ? "2x" : "快进"}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
