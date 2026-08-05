"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { logout, type UserInfo } from "@/lib/api";

const baseNav = [
  { href: "/", label: "当前对局", eyebrow: "TABLE" },
  { href: "/history", label: "历史记录", eyebrow: "ARCHIVE" },
];

const adminNav = [
  { href: "/admin/models", label: "模型配置", eyebrow: "MODELS" },
  { href: "/admin/personas", label: "AI 人格", eyebrow: "PERSONAS" },
];

export default function Header({ user }: { user: UserInfo | null }) {
  const router = useRouter();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const navItems = user?.role === "admin" ? [...baseNav, ...adminNav] : baseNav;

  async function handleLogout() {
    await logout();
    setMobileOpen(false);
    router.replace("/login");
  }

  function navLinkClass(href: string) {
    const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
    return `focus-ring group flex items-center gap-2 rounded-xl px-3 py-2 transition-colors ${
      active ? "bg-gold/10 text-bone" : "text-smoke hover:bg-white/5 hover:text-bone"
    }`;
  }

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-ink-950/85 backdrop-blur-xl">
      <div className="mx-auto flex min-h-[68px] max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
        <Link href="/" className="focus-ring flex min-w-0 items-center gap-3 rounded-xl" onClick={() => setMobileOpen(false)}>
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-gold/30 bg-gold/10 text-xl text-gold shadow-[0_0_24px_rgb(200_155_60_/_12%)]">
            ☾
          </span>
          <span className="min-w-0 leading-none">
            <span className="block truncate font-serif text-lg font-semibold tracking-wide text-bone">
              AI<span className="text-gold">狼人杀</span>
            </span>
            <span className="mt-1 block text-[9px] font-semibold uppercase tracking-[0.24em] text-smoke/70">暗夜审判厅</span>
          </span>
        </Link>

        <nav aria-label="主导航" className="hidden items-center gap-1 md:flex">
          {navItems.map((item) => (
            <Link key={item.href} href={item.href} className={navLinkClass(item.href)}>
              <span className="hidden text-[9px] font-semibold uppercase tracking-[0.16em] text-gold/75 lg:inline">{item.eyebrow}</span>
              <span className="text-sm">{item.label}</span>
            </Link>
          ))}
        </nav>

        <div className="hidden items-center gap-3 md:flex">
          {user && (
            <div className="flex items-center gap-2 border-l border-white/10 pl-4">
              <span className="flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-ink-800 text-xs font-semibold text-gold">
                {user.username.slice(0, 1).toUpperCase()}
              </span>
              <div className="leading-tight">
                <div className="max-w-[120px] truncate text-sm text-bone">{user.username}</div>
                {user.role === "admin" && <div className="text-[10px] text-gold">管理员</div>}
              </div>
            </div>
          )}
          {user && (
            <button className="btn-subtle px-2.5 py-2 text-xs" onClick={handleLogout}>
              退出
            </button>
          )}
        </div>

        <button
          type="button"
          aria-label={mobileOpen ? "关闭导航" : "打开导航"}
          aria-expanded={mobileOpen}
          className="btn-ghost px-3 py-2 md:hidden"
          onClick={() => setMobileOpen((open) => !open)}
        >
          <span className="text-lg leading-none">{mobileOpen ? "×" : "☰"}</span>
        </button>
      </div>

      {mobileOpen && (
        <div className="border-t border-white/10 bg-ink-900/95 px-4 py-3 md:hidden">
          <nav aria-label="移动端主导航" className="space-y-1">
            {navItems.map((item) => (
              <Link key={item.href} href={item.href} className={navLinkClass(item.href)} onClick={() => setMobileOpen(false)}>
                <span className="w-16 text-[9px] font-semibold uppercase tracking-[0.16em] text-gold/75">{item.eyebrow}</span>
                <span className="text-sm">{item.label}</span>
              </Link>
            ))}
          </nav>
          {user && (
            <div className="mt-3 flex items-center justify-between border-t border-white/10 pt-3">
              <div className="text-sm text-smoke">
                {user.username}
                {user.role === "admin" && <span className="ml-2 text-xs text-gold">管理员</span>}
              </div>
              <button className="btn-subtle px-2.5 py-2 text-xs" onClick={handleLogout}>
                退出
              </button>
            </div>
          )}
        </div>
      )}
    </header>
  );
}
