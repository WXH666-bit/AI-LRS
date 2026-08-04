"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { logout, type UserInfo } from "@/lib/api";

export default function Header({ user }: { user: UserInfo | null }) {
  const router = useRouter();
  return (
    <header className="border-b border-night-600/60 bg-night-900/80 backdrop-blur sticky top-0 z-20">
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
        <Link href="/" className="text-lg font-bold tracking-wider">
          🌙 AI<span className="text-amber-400">狼人杀</span>
        </Link>
        <nav className="flex items-center gap-1 text-sm">
          <Link href="/" className="px-3 py-1.5 rounded hover:bg-night-700">
            当前对局
          </Link>
          <Link href="/history" className="px-3 py-1.5 rounded hover:bg-night-700">
            历史记录
          </Link>
          {user?.role === "admin" && (
            <>
              <Link href="/admin/models" className="px-3 py-1.5 rounded hover:bg-night-700">
                模型配置
              </Link>
              <Link href="/admin/personas" className="px-3 py-1.5 rounded hover:bg-night-700">
                AI人格
              </Link>
            </>
          )}
          {user && (
            <span className="ml-3 text-slate-400">
              {user.username}
              {user.role === "admin" && <span className="ml-1 text-amber-400 text-xs">(管理员)</span>}
            </span>
          )}
          {user && (
            <button
              className="px-3 py-1.5 rounded hover:bg-night-700 text-slate-300"
              onClick={async () => {
                await logout();
                router.replace("/login");
              }}
            >
              退出
            </button>
          )}
        </nav>
      </div>
    </header>
  );
}
