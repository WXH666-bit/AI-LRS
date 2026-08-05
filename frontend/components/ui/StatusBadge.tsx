import type { ReactNode } from "react";

type StatusTone = "gold" | "danger" | "success" | "info" | "muted";

interface StatusBadgeProps {
  tone: StatusTone;
  children: ReactNode;
  className?: string;
}

const toneClasses: Record<StatusTone, string> = {
  gold: "border-gold/30 bg-gold/10 text-[#e7bd68]",
  danger: "border-cinnabar/30 bg-cinnabar/10 text-[#ef8f87]",
  success: "border-sage/30 bg-sage/10 text-[#9bd3c6]",
  info: "border-sky-300/25 bg-sky-300/10 text-sky-200",
  muted: "border-white/10 bg-white/5 text-smoke",
};

export default function StatusBadge({ tone, children, className = "" }: StatusBadgeProps) {
  return (
    <span className={`status-badge ${toneClasses[tone]} ${className}`}>
      <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-current" />
      {children}
    </span>
  );
}
