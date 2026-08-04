"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getMe, type UserInfo } from "./api";

/** 客户端登录守卫：未登录跳转 /login */
export function useUser() {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;
    getMe().then((u) => {
      if (cancelled) return;
      if (!u) {
        router.replace("/login");
        return;
      }
      setUser(u);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [router]);

  return { user, loading, setUser };
}
