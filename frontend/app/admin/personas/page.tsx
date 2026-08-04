"use client";

import { useEffect, useState } from "react";
import Header from "@/components/Header";
import { api } from "@/lib/api";
import type { Persona } from "@/lib/types";
import { useUser } from "@/lib/useUser";

const EMPTY: Persona = {
  id: 0,
  name: "",
  speaking_style: "",
  risk_preference: "",
  reasoning_style: "",
  aggression: 3,
  description: "",
};

export default function AdminPersonasPage() {
  const { user, loading } = useUser();
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [form, setForm] = useState<Persona>({ ...EMPTY });
  const [editingId, setEditingId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!user) return;
    api<{ personas: Persona[] }>("/admin/ai-personas").then((d) => setPersonas(d.personas)).catch(() => {});
  }, [user]);

  if (loading || !user) return <div className="min-h-screen" />;
  if (user.role !== "admin") return <div className="min-h-screen"><Header user={user} /><main className="p-8 text-center text-slate-400">需要管理员权限</main></div>;

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const body = { ...form };
      if (editingId) {
        await api(`/admin/ai-personas/${editingId}`, { method: "PATCH", body: JSON.stringify(body) });
      } else {
        await api("/admin/ai-personas", { method: "POST", body: JSON.stringify(body) });
      }
      setForm({ ...EMPTY });
      setEditingId(null);
      const d = await api<{ personas: Persona[] }>("/admin/ai-personas");
      setPersonas(d.personas);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen">
      <Header user={user} />
      <main className="max-w-4xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-6">AI 人格</h1>

        <form onSubmit={save} className="card p-5 mb-8 space-y-4">
          <h2 className="font-bold">{editingId ? `编辑 #${editingId}` : "新增人格"}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">名字</label>
              <input className="input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="如：小狼 / 沉稳大叔" />
            </div>
            <div>
              <label className="label">攻击性（1~5）</label>
              <input className="input" type="number" min={1} max={5} value={form.aggression} onChange={(e) => setForm({ ...form, aggression: Number(e.target.value) })} />
            </div>
            <div>
              <label className="label">发言风格</label>
              <input className="input" value={form.speaking_style} onChange={(e) => setForm({ ...form, speaking_style: e.target.value })} placeholder="如：话多爱带节奏 / 惜字如金" />
            </div>
            <div>
              <label className="label">风险偏好</label>
              <input className="input" value={form.risk_preference} onChange={(e) => setForm({ ...form, risk_preference: e.target.value })} placeholder="激进 / 保守 / 均衡" />
            </div>
            <div>
              <label className="label">推理风格</label>
              <input className="input" value={form.reasoning_style} onChange={(e) => setForm({ ...form, reasoning_style: e.target.value })} placeholder="如：逻辑严谨 / 直觉流" />
            </div>
          </div>
          <div>
            <label className="label">简介</label>
            <textarea className="input min-h-[60px]" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
          {error && <p className="text-red-400 text-sm">{error}</p>}
          <div className="flex gap-2">
            <button className="btn-primary" disabled={busy || !form.name}>{editingId ? "保存修改" : "添加人格"}</button>
            {editingId && (
              <button type="button" className="btn-ghost" onClick={() => { setEditingId(null); setForm({ ...EMPTY }); }}>
                取消
              </button>
            )}
          </div>
        </form>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {personas.map((p) => (
            <div key={p.id} className="card p-4">
              <div className="flex items-center justify-between mb-1">
                <span className="font-bold">{p.name}</span>
                <span className="text-xs text-slate-500">攻击性 {p.aggression}/5</span>
              </div>
              {(p.speaking_style || p.risk_preference || p.reasoning_style) && (
                <div className="text-xs text-slate-400 space-y-0.5">
                  {p.speaking_style && <div>风格：{p.speaking_style}</div>}
                  {p.risk_preference && <div>风险：{p.risk_preference}</div>}
                  {p.reasoning_style && <div>推理：{p.reasoning_style}</div>}
                </div>
              )}
              {p.description && <p className="text-xs text-slate-500 mt-1">{p.description}</p>}
              <div className="flex gap-2 mt-3">
                <button
                  className="btn-ghost text-xs"
                  onClick={() => {
                    setEditingId(p.id);
                    setForm({ ...p });
                  }}
                >
                  编辑
                </button>
                <button
                  className="btn-ghost text-xs text-red-300"
                  onClick={async () => {
                    if (confirm(`删除人格「${p.name}」？`)) {
                      await api(`/admin/ai-personas/${p.id}`, { method: "DELETE" });
                      const d = await api<{ personas: Persona[] }>("/admin/ai-personas");
                      setPersonas(d.personas);
                    }
                  }}
                >
                  删除
                </button>
              </div>
            </div>
          ))}
          {personas.length === 0 && <p className="text-slate-500 text-sm col-span-2">暂无人格。不同模型 + 不同人格可以互相比较表现。</p>}
        </div>
      </main>
    </div>
  );
}
