import type { DisplayLine } from "@/lib/formatEvent";

interface EventEntryProps {
  event: DisplayLine;
  isLatest?: boolean;
}

const eventMeta: Record<DisplayLine["kind"], { icon: string; className: string }> = {
  phase: { icon: "◈", className: "border-gold/25 bg-gold/5 text-[#e7bd68] text-center font-semibold" },
  public: { icon: "·", className: "border-white/8 bg-white/[0.02] text-bone" },
  wolf: { icon: "☽", className: "border-[#9b78c5]/25 bg-[#9b78c5]/5 text-[#c9b6e4]" },
  private: { icon: "◇", className: "border-sage/25 bg-sage/5 text-[#9bd3c6]" },
  death: { icon: "†", className: "border-cinnabar/25 bg-cinnabar/5 text-[#ef8f87]" },
  system: { icon: "✦", className: "border-sky-300/20 bg-sky-300/5 text-sky-200" },
  me: { icon: "◆", className: "border-gold/25 bg-gold/5 text-[#e7bd68]" },
};

export default function EventEntry({ event, isLatest = false }: EventEntryProps) {
  const meta = eventMeta[event.kind];
  return (
    <div className={`flex gap-3 rounded-xl border px-3.5 py-2.5 text-sm leading-6 transition-colors ${meta.className} ${isLatest ? "shadow-[0_0_24px_rgb(200_155_60_/_8%)]" : ""}`}>
      <span aria-hidden="true" className="w-4 shrink-0 text-center font-serif text-base opacity-80">{meta.icon}</span>
      <span className="min-w-0 break-words">{event.text}</span>
    </div>
  );
}
