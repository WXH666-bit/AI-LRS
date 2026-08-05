import Panel from "@/components/ui/Panel";
import StatusBadge from "@/components/ui/StatusBadge";
import type { RoleSetupItem } from "@/lib/types";

interface RoleRosterProps {
  items: RoleSetupItem[];
  revealed?: boolean;
}

const roleMarks: Record<string, string> = {
  wolf: "☾",
  seer: "◈",
  witch: "✦",
  hunter: "↗",
  guard: "◇",
  villager: "·",
};

const roleClasses: Record<string, string> = {
  wolf: "border-cinnabar/30 bg-cinnabar/10 text-[#ef8f87]",
  seer: "border-gold/30 bg-gold/10 text-[#e7bd68]",
  witch: "border-gold/30 bg-gold/10 text-[#e7bd68]",
  hunter: "border-sage/30 bg-sage/10 text-[#9bd3c6]",
  guard: "border-sage/30 bg-sage/10 text-[#9bd3c6]",
  villager: "border-white/10 bg-white/[0.03] text-smoke",
};

export default function RoleRoster({ items, revealed = false }: RoleRosterProps) {
  if (!items.length) return null;

  const maxCount = Math.max(...items.map((item) => item.count));

  return (
    <Panel
      className="overflow-hidden"
      title={
        <>
          <div className="eyebrow mb-2">ROLE MIX</div>
          <h2 className="font-serif text-xl font-semibold text-bone">本局角色配置</h2>
        </>
      }
      actions={revealed ? <StatusBadge tone="danger">管理员视角</StatusBadge> : <span className="text-xs text-smoke">公开信息</span>}
    >
      <div className="p-4 sm:p-5">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
          {items.map((item) => (
            <div key={item.role} className={`rounded-2xl border px-3 py-3 ${roleClasses[item.role] || roleClasses.villager}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="flex min-w-0 items-center gap-2 text-sm font-semibold">
                  <span aria-hidden="true" className="text-base leading-none">{roleMarks[item.role] || "•"}</span>
                  <span className="truncate">{item.label}</span>
                </span>
                <span className="font-mono text-lg font-semibold leading-none">×{item.count}</span>
              </div>
              <div className="mt-3 h-1 overflow-hidden rounded-full bg-black/20">
                <div className="h-full rounded-full bg-current opacity-70" style={{ width: `${(item.count / maxCount) * 100}%` }} />
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-white/8 pt-3 text-xs text-smoke">
          <span>{revealed ? "管理员观战：每个座位的身份已公开" : "只显示角色数量，不代表具体座位身份"}</span>
          <span className="font-mono text-[10px] tracking-[0.14em] text-gold">{items.reduce((total, item) => total + item.count, 0)} PLAYERS</span>
        </div>
      </div>
    </Panel>
  );
}
