"use client";

import { useEffect, useState } from "react";
import Header from "@/components/Header";
import EmptyState from "@/components/ui/EmptyState";
import Panel from "@/components/ui/Panel";
import StatusBadge from "@/components/ui/StatusBadge";
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

const TIMEOUT_PRESETS = [30, 60, 90, 120, 180] as const;
const CUSTOM_TIMEOUT = "custom";
type TimeoutMode = `${(typeof TIMEOUT_PRESETS)[number]}` | typeof CUSTOM_TIMEOUT;

function timeoutChoice(seconds: number): TimeoutMode {
  return TIMEOUT_PRESETS.includes(seconds as (typeof TIMEOUT_PRESETS)[number]) ? String(seconds) as TimeoutMode : CUSTOM_TIMEOUT;
}

export default function AdminModelsPage() {
  const { user, loading } = useUser();
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [timeoutMode, setTimeoutMode] = useState<TimeoutMode>(timeoutChoice(EMPTY_FORM.timeout_seconds));
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
      const data = await api<{ models: ModelConfig[] }>("/admin/model-configs");
      setModels(data.models);
    } catch {
      /* ignore */
    }
  }

  if (loading || !user) return <div className="min-h-screen" />;
  if (user.role !== "admin") return <div className="min-h-screen"><Header user={user} /><main className="p-8 text-center text-smoke">需要管理员权限</main></div>;

  async function save(event: React.FormEvent) {
    event.preventDefault();
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
      setTimeoutMode(timeoutChoice(EMPTY_FORM.timeout_seconds));
      setEditingId(null);
      await load();
    } catch (err: any) {
      setError(err.message || "保存失败，请检查配置");
    } finally {
      setBusy(false);
    }
  }

  async function testModel(model: ModelConfig) {
    setTestingId(model.id);
    setTestResult((previous) => ({ ...previous, [model.id]: "测试中…" }));
    try {
      const result = await api<{ ok: boolean; latency_ms: number; message: string }>(`/admin/model-configs/${model.id}/test`, { method: "POST" });
      setTestResult((previous) => ({ ...previous, [model.id]: result.message }));
    } catch (err: any) {
      setTestResult((previous) => ({ ...previous, [model.id]: err.message || "连接失败" }));
    } finally {
      setTestingId(null);
    }
  }

  function resetForm() {
    setEditingId(null);
    setForm({ ...EMPTY_FORM });
    setTimeoutMode(timeoutChoice(EMPTY_FORM.timeout_seconds));
    setError("");
  }

  return (
    <div className="min-h-screen">
      <Header user={user} />
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:py-12">
        <div className="mb-8">
          <div className="eyebrow mb-3">CONTROL ROOM · MODELS</div>
          <h1 className="font-serif text-4xl font-semibold tracking-tight text-bone">模型配置</h1>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-smoke">管理连接信息、生成参数和 AI 发言时的运行边界。测试连接只验证模型是否可达，不会开始一场对局。</p>
        </div>

        <form onSubmit={save} className="panel mb-8 overflow-hidden">
          <div className="border-b border-white/10 bg-gradient-to-r from-gold/10 to-transparent px-5 py-5 sm:px-7">
            <div className="eyebrow mb-2">{editingId ? `EDIT MODEL #${editingId}` : "NEW MODEL"}</div>
            <h2 className="font-serif text-2xl font-semibold text-bone">{editingId ? "编辑模型" : "添加一个模型"}</h2>
          </div>

          <div className="grid gap-8 p-5 sm:p-7 xl:grid-cols-[minmax(0,1fr)_320px]">
            <section>
              <div className="mb-4 text-xs font-semibold uppercase tracking-[0.16em] text-smoke">连接信息</div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="label" htmlFor="model-display-name">显示名称</label>
                  <input id="model-display-name" className="input" required value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} placeholder="如：GLM-5 / Qwen-Max" />
                </div>
                <div>
                  <label className="label" htmlFor="model-protocol">协议</label>
                  <select id="model-protocol" className="input" value={form.protocol} onChange={(e) => setForm({ ...form, protocol: e.target.value as any })}>
                    <option value="openai_compatible">OpenAI 兼容</option>
                    <option value="anthropic_messages">Anthropic Messages</option>
                  </select>
                </div>
                <div className="sm:col-span-2">
                  <label className="label" htmlFor="model-base-url">Base URL</label>
                  <input id="model-base-url" className="input font-mono text-xs" required value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} placeholder="https://api.openai.com/v1" />
                </div>
                <div>
                  <label className="label" htmlFor="model-name">模型名</label>
                  <input id="model-name" className="input font-mono text-xs" required value={form.model_name} onChange={(e) => setForm({ ...form, model_name: e.target.value })} placeholder="glm-5 / qwen-max" />
                </div>
                <div>
                  <label className="label" htmlFor="model-api-key">API Key {editingId && "（留空保持不变）"}</label>
                  <input id="model-api-key" className="input font-mono text-xs" type="password" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} placeholder="sk-…" />
                </div>
              </div>
            </section>

            <section className="border-t border-white/10 pt-6 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
              <div className="mb-4 text-xs font-semibold uppercase tracking-[0.16em] text-smoke">生成参数</div>
              <div className="space-y-4">
                <div>
                  <label className="label" htmlFor="model-temperature">温度</label>
                  <div className="flex items-center gap-3">
                    <input id="model-temperature" className="input" type="number" step="0.1" min="0" max="2" value={form.temperature} onChange={(e) => setForm({ ...form, temperature: Number(e.target.value) })} />
                    <span className="shrink-0 text-xs text-smoke">0–2</span>
                  </div>
                </div>
                <div>
                  <label className="label" htmlFor="model-timeout">超时（秒）</label>
                  <select id="model-timeout" className="input" value={timeoutMode} onChange={(e) => {
                    const value = e.target.value as TimeoutMode;
                    setTimeoutMode(value);
                    if (value !== CUSTOM_TIMEOUT) setForm({ ...form, timeout_seconds: Number(value) });
                  }}>
                    {TIMEOUT_PRESETS.map((seconds) => <option key={seconds} value={seconds}>{seconds} 秒</option>)}
                    <option value={CUSTOM_TIMEOUT}>自定义</option>
                  </select>
                  {timeoutMode === CUSTOM_TIMEOUT && <input className="input mt-2" type="number" min="1" max="300" value={form.timeout_seconds} onChange={(e) => setForm({ ...form, timeout_seconds: Number(e.target.value) })} aria-label="自定义超时（秒）" />}
                  <p className="mt-2 text-xs leading-5 text-smoke/70">完整发言会受到此超时限制，过短可能触发兜底发言。</p>
                </div>
                <div>
                  <label className="label" htmlFor="model-max-tokens">Max Tokens</label>
                  <input id="model-max-tokens" className="input" type="number" min="1" value={form.max_output_tokens} onChange={(e) => setForm({ ...form, max_output_tokens: Number(e.target.value) })} />
                </div>
              </div>
            </section>
          </div>

          <div className="flex flex-wrap items-center gap-4 border-t border-white/10 px-5 py-4 sm:px-7">
            <label className="flex items-center gap-2 text-sm text-bone"><input type="checkbox" className="accent-[#c89b3c]" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />启用此模型</label>
            <label className="flex items-center gap-2 text-sm text-smoke"><input type="checkbox" className="accent-[#c89b3c]" checked={form.is_default_fallback} onChange={(e) => setForm({ ...form, is_default_fallback: e.target.checked })} />作为默认兜底</label>
          </div>

          {error && <div role="alert" className="mx-5 mb-4 rounded-xl border border-cinnabar/30 bg-cinnabar/10 px-4 py-3 text-sm text-[#ef8f87] sm:mx-7">{error}</div>}
          <div className="flex gap-2 border-t border-white/10 px-5 py-4 sm:px-7">
            <button className="btn-primary" disabled={busy} aria-busy={busy}>{busy ? "保存中…" : editingId ? "保存修改" : "添加模型"}</button>
            {editingId && <button type="button" className="btn-ghost" onClick={resetForm}>取消</button>}
          </div>
        </form>

        <div className="mb-4 flex items-end justify-between gap-4">
          <div><div className="eyebrow mb-2">MODEL REGISTRY</div><h2 className="font-serif text-2xl font-semibold text-bone">已配置模型</h2></div>
          <span className="text-xs text-smoke">{models.length} 个配置</span>
        </div>
        {models.length === 0 ? (
          <EmptyState eyebrow="NO MODELS" title="还没有模型配置" description="添加一个兼容 OpenAI 或 Anthropic Messages 的模型，AI 才能开始发言。" />
        ) : (
          <div className="space-y-3">
            {models.map((model) => (
              <Panel key={model.id} className="p-5 sm:p-6">
                <div className="flex flex-col justify-between gap-5 xl:flex-row xl:items-center">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-serif text-xl font-semibold text-bone">{model.display_name}</h3>
                      <StatusBadge tone={model.enabled ? "success" : "muted"}>{model.enabled ? "已启用" : "已停用"}</StatusBadge>
                      {model.is_default_fallback && <StatusBadge tone="gold">默认兜底</StatusBadge>}
                      <StatusBadge tone={model.has_api_key ? "info" : "danger"}>{model.has_api_key ? "密钥已配置" : "未配置密钥"}</StatusBadge>
                    </div>
                    <div className="mt-3 truncate font-mono text-xs text-smoke">{model.protocol === "anthropic_messages" ? "Anthropic" : "OpenAI 兼容"} · {model.base_url} · {model.model_name}</div>
                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-smoke/75"><span>温度 {model.temperature}</span><span>超时 {model.timeout_seconds}s</span><span>输出上限 {model.max_output_tokens}</span></div>
                    {testResult[model.id] && <div className={`mt-3 text-xs ${testResult[model.id].includes("成功") ? "text-[#9bd3c6]" : "text-[#ef8f87]"}`}>{testResult[model.id]}</div>}
                  </div>
                  <div className="flex flex-wrap gap-2 xl:justify-end">
                    <button className="btn-ghost text-xs" disabled={testingId === model.id} onClick={() => testModel(model)}>{testingId === model.id ? "测试中…" : "测试连接"}</button>
                    <button className="btn-ghost text-xs" onClick={() => { setEditingId(model.id); setTimeoutMode(timeoutChoice(model.timeout_seconds)); setForm({ display_name: model.display_name, protocol: model.protocol, base_url: model.base_url, model_name: model.model_name, api_key: "", temperature: model.temperature, max_output_tokens: model.max_output_tokens, timeout_seconds: model.timeout_seconds, enabled: model.enabled, is_default_fallback: model.is_default_fallback }); window.scrollTo({ top: 0, behavior: "smooth" }); }}>编辑</button>
                    <button className="btn-ghost text-xs text-[#ef8f87]" onClick={async () => { if (confirm(`删除模型「${model.display_name}」？`)) { await api(`/admin/model-configs/${model.id}`, { method: "DELETE" }); await load(); } }}>删除</button>
                  </div>
                </div>
              </Panel>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
