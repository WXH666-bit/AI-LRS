"use client";

import { useEffect, useState } from "react";
import Header from "@/components/Header";
import EmptyState from "@/components/ui/EmptyState";
import Panel from "@/components/ui/Panel";
import StatusBadge from "@/components/ui/StatusBadge";
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
    api<{ personas: Persona[] }>("/admin/ai-personas").then((data) => setPersonas(data.personas)).catch(() => {});
  }, [user]);

  if (loading || !user) return <div className="min-h-screen" />;
  if (user.role !== "admin") return <div className="min-h-screen"><Header user={user} /><main className="p-8 text-center text-smoke">需要管理员权限</main></div>;

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (editingId) {
        await api(`/admin/ai-personas/${editingId}`, { method: "PATCH", body: JSON.stringify({ ...form }) });
      } else {
        await api("/admin/ai-personas", { method: "POST", body: JSON.stringify({ ...form }) });
      }
      setForm({ ...EMPTY });
      setEditingId(null);
      const data = await api<{ personas: Persona[] }>("/admin/ai-personas");
      setPersonas(data.personas);
    } catch (err: any) {
      setError(err.message || "保存失败，请检查人格设定");
    } finally {
      setBusy(false);
    }
  }

  function resetForm() {
    setEditingId(null);
    setForm({ ...EMPTY });
    setError("");
  }

  return (
    <div className="min-h-screen">
      <Header user={user} />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:py-12">
        <div className="mb-8">
          <div className="eyebrow mb-3">CONTROL ROOM · PERSONAS</div>
          <h1 className="font-serif text-4xl font-semibold tracking-tight text-bone">AI 人格档案</h1>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-smoke">给每个 AI 一套可辨认的性格。风格不是装饰，它会改变牌桌上的判断方式。</p>
        </div>

        <form onSubmit={save} className="panel mb-10 overflow-hidden">
          <div className="border-b border-white/10 bg-gradient-to-r from-gold/10 to-transparent px-5 py-5 sm:px-7">
            <div className="eyebrow mb-2">{editingId ? `EDIT PERSONA #${editingId}` : "NEW PERSONA"}</div>
            <h2 className="font-serif text-2xl font-semibold text-bone">{editingId ? "编辑人格" : "创建人格"}</h2>
          </div>
          <div className="grid gap-8 p-5 sm:p-7 xl:grid-cols-[280px_minmax(0,1fr)]">
            <section>
              <div className="mb-4 text-xs font-semibold uppercase tracking-[0.16em] text-smoke">人格签名</div>
              <div className="space-y-4">
                <div>
                  <label className="label" htmlFor="persona-name">名字</label>
                  <input id="persona-name" className="input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="如：沉稳大叔" />
                </div>
                <div>
                  <label className="label" htmlFor="persona-aggression">攻击性（1–5）</label>
                  <div className="flex items-center gap-3">
                    <input id="persona-aggression" className="input" type="number" min={1} max={5} value={form.aggression} onChange={(e) => setForm({ ...form, aggression: Number(e.target.value) })} />
                    <span className="shrink-0 text-xs text-smoke">{form.aggression}/5</span>
                  </div>
                </div>
                <div className="rounded-xl border border-gold/20 bg-gold/5 p-4 text-sm leading-6 text-smoke">
                  <span className="text-[#e7bd68]">提示：</span> 高攻击性会更主动地质疑、施压和带动投票；低攻击性更倾向于观察和保留意见。
                </div>
              </div>
            </section>

            <section className="border-t border-white/10 pt-6 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
              <div className="mb-4 text-xs font-semibold uppercase tracking-[0.16em] text-smoke">行为参数</div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="label" htmlFor="persona-speaking">发言风格</label>
                  <input id="persona-speaking" className="input" value={form.speaking_style} onChange={(e) => setForm({ ...form, speaking_style: e.target.value })} placeholder="话多爱带节奏 / 惜字如金" />
                </div>
                <div>
                  <label className="label" htmlFor="persona-risk">风险偏好</label>
                  <input id="persona-risk" className="input" value={form.risk_preference} onChange={(e) => setForm({ ...form, risk_preference: e.target.value })} placeholder="激进 / 保守 / 均衡" />
                </div>
                <div className="sm:col-span-2">
                  <label className="label" htmlFor="persona-reasoning">推理风格</label>
                  <input id="persona-reasoning" className="input" value={form.reasoning_style} onChange={(e) => setForm({ ...form, reasoning_style: e.target.value })} placeholder="逻辑严谨 / 直觉流 / 先验派" />
                </div>
                <div className="sm:col-span-2">
                  <label className="label" htmlFor="persona-description">简介</label>
                  <textarea id="persona-description" className="input min-h-[96px] resize-y" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="写一句让你能记住这个人格的话。" />
                </div>
              </div>
            </section>
          </div>
          {error && <div role="alert" className="mx-5 mb-4 rounded-xl border border-cinnabar/30 bg-cinnabar/10 px-4 py-3 text-sm text-[#ef8f87] sm:mx-7">{error}</div>}
          <div className="flex gap-2 border-t border-white/10 px-5 py-4 sm:px-7">
            <button className="btn-primary" disabled={busy || !form.name} aria-busy={busy}>{busy ? "保存中…" : editingId ? "保存修改" : "添加人格"}</button>
            {editingId && <button type="button" className="btn-ghost" onClick={resetForm}>取消</button>}
          </div>
        </form>

        <div className="mb-4 flex items-end justify-between gap-4">
          <div><div className="eyebrow mb-2">PERSONA ARCHIVE</div><h2 className="font-serif text-2xl font-semibold text-bone">已有的人格</h2></div>
          <span className="text-xs text-smoke">{personas.length} 个档案</span>
        </div>
        {personas.length === 0 ? (
          <EmptyState eyebrow="NO PERSONAS" title="还没有 AI 人格" description="先创建一套性格，下一场对局里就能观察它如何做出判断。" />
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {personas.map((persona) => (
              <Panel key={persona.id} className="group p-5 transition-colors hover:border-gold/30 sm:p-6">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-gold/20 bg-gold/10 font-serif text-xl text-gold">{persona.name.slice(0, 1)}</div>
                    <div className="min-w-0"><h3 className="truncate font-serif text-xl font-semibold text-bone">{persona.name}</h3><p className="mt-1 text-xs text-smoke">人格档案 #{String(persona.id).padStart(2, "0")}</p></div>
                  </div>
                  <StatusBadge tone={persona.aggression >= 4 ? "danger" : persona.aggression <= 2 ? "muted" : "gold"}>攻击性 {persona.aggression}/5</StatusBadge>
                </div>
                <div className="mt-5 grid gap-2 text-xs text-smoke">
                  {persona.speaking_style && <div className="flex gap-3"><span className="w-12 shrink-0 text-gold/80">发言</span><span>{persona.speaking_style}</span></div>}
                  {persona.risk_preference && <div className="flex gap-3"><span className="w-12 shrink-0 text-gold/80">风险</span><span>{persona.risk_preference}</span></div>}
                  {persona.reasoning_style && <div className="flex gap-3"><span className="w-12 shrink-0 text-gold/80">推理</span><span>{persona.reasoning_style}</span></div>}
                </div>
                {persona.description && <p className="mt-5 border-t border-white/10 pt-4 text-sm leading-6 text-smoke">{persona.description}</p>}
                <div className="mt-5 flex gap-2 border-t border-white/10 pt-4">
                  <button className="btn-ghost text-xs" onClick={() => { setEditingId(persona.id); setForm({ ...persona }); window.scrollTo({ top: 0, behavior: "smooth" }); }}>编辑</button>
                  <button className="btn-ghost text-xs text-[#ef8f87]" onClick={async () => { if (confirm(`删除人格「${persona.name}」？`)) { await api(`/admin/ai-personas/${persona.id}`, { method: "DELETE" }); const data = await api<{ personas: Persona[] }>("/admin/ai-personas"); setPersonas(data.personas); } }}>删除</button>
                </div>
              </Panel>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
