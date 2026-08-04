"use client";

import { useEffect, useState } from "react";
import Header from "@/components/Header";
import { api } from "@/lib/api";
import type { ModelConfig } from "@/lib/types";
import { useUser } from "@/lib/useUser";

const EMPTY_FORM = {
  display_name: "",
  protocol: "openai_compatible",
  base_url: "",
  model_name: "",
  api_key: "",
  temperature: 0.9,
  max_output_tokens: 2048,
  timeout_seconds: 30,
  enabled: true,
  is_default_fallback: false,
};

export default function AdminModelsPage() {
  const { user, loading } = useUser();
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [editingId, setEditingId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [testingId, setTestingId] = useState<number | null>(null);
  const [testResult, setTestResult] = useState<Record<number, string>>({});

  useEffect(() => {
    if (!user) return;
    load();
  }, [user]);

  async function load() {
    try {
      const d = await api<{ models: ModelConfig[] }>("/admin/model-configs");
      setModels(d.models);
    } catch {
      /* ignore */
    }
  }

  if (loading || !user) return <div className="min-h-screen" />;
  if (user.role !== "admin") return <div className="min-h-screen"><Header user={user} /><main className="p-8 text-center text-slate-400">需要管理员权限</main></div>;

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const body = { ...form, api_key: form.api_key || undefined };
      if (editingId) {
        await api(`/admin/model-configs/${editingId}`, { method: "PATCH", body: JSON.stringify(body) });
      } else {
        await api("/admin/model-configs", { method: "POST", body: JSON.stringify(body) });
      }
      setForm({ ...EMPTY_FORM });
      setEditingId(null);
      await load();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function testModel(m: ModelConfig) {
    setTestingId(m.id);
    setTestResult((r) => ({ ...r, [m.id]: "测试中…" }));
    try {
      const r = await api<{ ok: boolean; latency_ms: number; message: string }>(`/admin/model-configs/${m.id}/test`, { method: "POST" });
      setTestResult((prev) => ({ ...prev, [m.id]: r.message }));
    } catch (err: any) {
      setTestResult((prev) => ({ ...prev, [m.id]: err.message }));
    } finally {
      setTestingId(null);
    }
  }

  return (
    <div className="min-h-screen">
      <Header user={user} />
      <main className="max-w-4xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-6">模型配置</h1>

        {/* 表单 */}
        <form onSubmit={save} className="card p-5 mb-8 space-y-4">
          <h2 className="font-bold">{editingId ? `编辑 #${editingId}` : "新增模型"}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">显示名称</label>
              <input className="input" required value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} placeholder="如：Claude Sonnet / Qwen-Max / GLM-4" />
            </div>
            <div>
              <label className="label">协议</label>
              <select className="input" value={form.protocol} onChange={(e) => setForm({ ...form, protocol: e.target.value as any })}>
                <option value="openai_compatible">OpenAI 兼容</option>
                <option value="anthropic_messages">Anthropic Messages</option>
              </select>
            </div>
            <div>
              <label className="label">Base URL</label>
              <input className="input" required value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} placeholder="https://api.openai.com/v1 或 /compatible-mode/v1 等" />
            </div>
            <div>
              <label className="label">模型名</label>
              <input className="input" required value={form.model_name} onChange={(e) => setForm({ ...form, model_name: e.target.value })} placeholder="gpt-4o / qwen-max / glm-4-plus" />
            </div>
            <div>
              <label className="label">API Key {editingId && "(留空保持不变)"}</label>
              <input className="input" type="password" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} placeholder="sk-..." />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="label">温度</label>
                <input className="input" type="number" step="0.1" min="0" max="2" value={form.temperature} onChange={(e) => setForm({ ...form, temperature: Number(e.target.value) })} />
              </div>
              <div>
                <label className="label">超时(秒)</label>
                <input className="input" type="number" min="1" max="300" value={form.timeout_seconds} onChange={(e) => setForm({ ...form, timeout_seconds: Number(e.target.value) })} />
              </div>
              <div>
                <label className="label">Max Tokens</label>
                <input className="input" type="number" min="1" value={form.max_output_tokens} onChange={(e) => setForm({ ...form, max_output_tokens: Number(e.target.value) })} />
              </div>
            </div>
          </div>
          <div className="flex items-center gap-6 text-sm">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
              启用
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={form.is_default_fallback} onChange={(e) => setForm({ ...form, is_default_fallback: e.target.checked })} />
              作为默认兜底模型（AI托管/未指定时使用）
            </label>
          </div>
          {error && <p className="text-red-400 text-sm">{error}</p>}
          <div className="flex gap-2">
            <button className="btn-primary" disabled={busy}>{editingId ? "保存修改" : "添加模型"}</button>
            {editingId && (
              <button type="button" className="btn-ghost" onClick={() => { setEditingId(null); setForm({ ...EMPTY_FORM }); }}>
                取消
              </button>
            )}
          </div>
        </form>

        {/* 列表 */}
        <div className="space-y-3">
          {models.map((m) => (
            <div key={m.id} className="card p-4 flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="font-bold">
                  {m.display_name}
                  {m.is_default_fallback && <span className="ml-2 text-[10px] bg-amber-500/20 text-amber-300 px-1.5 py-0.5 rounded">默认兜底</span>}
                  {!m.enabled && <span className="ml-2 text-[10px] bg-slate-700 px-1.5 py-0.5 rounded text-slate-400">已停用</span>}
                </div>
                <div className="text-xs text-slate-500 mt-1 font-mono truncate">
                  {m.protocol === "anthropic_messages" ? "Anthropic" : "OpenAI兼容"} · {m.base_url} · {m.model_name}
                </div>
                <div className="text-xs text-slate-600 mt-0.5">
                  温度 {m.temperature} · 超时 {m.timeout_seconds}s · 密钥{m.has_api_key ? "已配置" : "未配置"}
                </div>
                {testResult[m.id] && (
                  <div className={`text-xs mt-1 ${testResult[m.id].startsWith("连接成功") ? "text-emerald-400" : "text-red-400"}`}>
                    {testResult[m.id]}
                  </div>
                )}
              </div>
              <div className="flex gap-2 shrink-0">
                <button className="btn-ghost text-xs" disabled={testingId === m.id} onClick={() => testModel(m)}>
                  {testingId === m.id ? "测试中…" : "测试连接"}
                </button>
                <button
                  className="btn-ghost text-xs"
                  onClick={() => {
                    setEditingId(m.id);
                    setForm({
                      display_name: m.display_name,
                      protocol: m.protocol,
                      base_url: m.base_url,
                      model_name: m.model_name,
                      api_key: "",
                      temperature: m.temperature,
                      max_output_tokens: m.max_output_tokens,
                      timeout_seconds: m.timeout_seconds,
                      enabled: m.enabled,
                      is_default_fallback: m.is_default_fallback,
                    });
                  }}
                >
                  编辑
                </button>
                <button
                  className="btn-ghost text-xs text-red-300"
                  onClick={async () => {
                    if (confirm(`删除模型「${m.display_name}」？`)) {
                      await api(`/admin/model-configs/${m.id}`, { method: "DELETE" });
                      await load();
                    }
                  }}
                >
                  删除
                </button>
              </div>
            </div>
          ))}
          {models.length === 0 && <p className="text-slate-500 text-sm">暂无模型配置。支持：OpenAI、Qwen（阿里云百炼）、GLM（智谱）等 OpenAI 兼容服务，以及 Claude（Anthropic Messages）。</p>}
        </div>
      </main>
    </div>
  );
}
