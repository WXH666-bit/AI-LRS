import type { ReactNode } from "react";

interface EmptyStateProps {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}

export default function EmptyState({ eyebrow, title, description, action }: EmptyStateProps) {
  return (
    <div className="panel flex flex-col items-center px-6 py-16 text-center">
      <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-2xl border border-gold/25 bg-gold/10 text-2xl text-gold shadow-[0_0_35px_rgb(200_155_60_/_12%)]">
        ☾
      </div>
      {eyebrow && <div className="eyebrow mb-3">{eyebrow}</div>}
      <h2 className="font-serif text-2xl font-semibold tracking-wide text-bone">{title}</h2>
      {description && <p className="mt-3 max-w-md text-sm leading-6 text-smoke">{description}</p>}
      {action && <div className="mt-7">{action}</div>}
    </div>
  );
}
