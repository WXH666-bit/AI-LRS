"""模型适配器：OpenAI 兼容协议 + Anthropic Messages 协议。"""
import json
import time
from collections.abc import Awaitable, Callable

import httpx

from ..models import ModelConfig

StreamCallback = Callable[[str], Awaitable[None]]


class ModelCallError(Exception):
    def __init__(self, message: str, kind: str = "error"):
        super().__init__(message)
        self.message = message
        self.kind = kind  # error | timeout | rate_limit


def _base_url(cfg: ModelConfig) -> str:
    return cfg.base_url.rstrip("/")


async def call_model(cfg: ModelConfig, api_key: str, system: str, user: str,
                     temperature: float | None = None, max_tokens: int | None = None) -> tuple[str, dict]:
    """调用模型，返回 (文本内容, 用量)。失败抛 ModelCallError。"""
    temperature = cfg.temperature if temperature is None else temperature
    max_tokens = cfg.max_output_tokens if max_tokens is None else max_tokens
    timeout = cfg.timeout_seconds or 30
    if cfg.protocol == "anthropic_messages":
        return await _call_anthropic(cfg, api_key, system, user, temperature, max_tokens, timeout)
    return await _call_openai_compatible(cfg, api_key, system, user, temperature, max_tokens, timeout)


async def call_model_stream(cfg: ModelConfig, api_key: str, system: str, user: str,
                            on_delta: StreamCallback,
                            temperature: float | None = None,
                            max_tokens: int | None = None) -> tuple[str, dict]:
    """以 SSE 增量调用模型；回调只接收文本，不改变最终解析流程。"""
    temperature = cfg.temperature if temperature is None else temperature
    max_tokens = cfg.max_output_tokens if max_tokens is None else max_tokens
    timeout = cfg.timeout_seconds or 30
    if cfg.protocol == "anthropic_messages":
        return await _stream_anthropic(cfg, api_key, system, user, temperature, max_tokens, timeout, on_delta)
    return await _stream_openai_compatible(cfg, api_key, system, user, temperature, max_tokens, timeout, on_delta)


async def _call_openai_compatible(cfg: ModelConfig, api_key: str, system: str, user: str,
                                  temperature: float, max_tokens: int, timeout: int) -> tuple[str, dict]:
    url = f"{_base_url(cfg)}/chat/completions"
    body = {
        "model": cfg.model_name,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            # 部分兼容服务不支持 response_format，失败时去掉重试一次
            body_json = dict(body)
            body_json["response_format"] = {"type": "json_object"}
            resp = await client.post(url, headers=headers, json=body_json)
            if resp.status_code == 400 and "response_format" in body_json:
                body_json.pop("response_format")
                resp = await client.post(url, headers=headers, json=body_json)
            if resp.status_code == 429:
                raise ModelCallError(f"限流 429: {resp.text[:200]}", kind="rate_limit")
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage") or {}
            return content or "", {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
            }
    except ModelCallError:
        raise
    except httpx.TimeoutException:
        raise ModelCallError(f"请求超时（{timeout}s）", kind="timeout")
    except httpx.HTTPStatusError as e:
        raise ModelCallError(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        raise ModelCallError(f"请求失败: {e}")


async def _stream_openai_compatible(cfg: ModelConfig, api_key: str, system: str, user: str,
                                    temperature: float, max_tokens: int, timeout: int,
                                    on_delta: StreamCallback) -> tuple[str, dict]:
    url = f"{_base_url(cfg)}/chat/completions"
    body = {
        "model": cfg.model_name,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    content: list[str] = []
    usage: dict = {}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            async with client.stream("POST", url, headers=headers, json=body) as resp:
                if resp.status_code == 429:
                    raise ModelCallError(f"限流 429: {await resp.aread()}", kind="rate_limit")
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if raw == "[DONE]":
                        break
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    chunk_usage = data.get("usage")
                    if chunk_usage:
                        usage = {
                            "prompt_tokens": chunk_usage.get("prompt_tokens", 0),
                            "completion_tokens": chunk_usage.get("completion_tokens", 0),
                        }
                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    delta = (choices[0].get("delta") or {}).get("content")
                    if delta:
                        content.append(delta)
                        await on_delta(delta)
        return "".join(content), usage
    except ModelCallError:
        raise
    except httpx.TimeoutException:
        raise ModelCallError(f"请求超时（{timeout}s）", kind="timeout")
    except httpx.HTTPStatusError as e:
        raise ModelCallError(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        raise ModelCallError(f"请求失败: {e}")


async def _call_anthropic(cfg: ModelConfig, api_key: str, system: str, user: str,
                          temperature: float, max_tokens: int, timeout: int) -> tuple[str, dict]:
    url = f"{_base_url(cfg)}/v1/messages"
    body = {
        "model": cfg.model_name,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            resp = await client.post(url, headers=headers, json=body)
            if resp.status_code == 429:
                raise ModelCallError(f"限流 429: {resp.text[:200]}", kind="rate_limit")
            resp.raise_for_status()
            data = resp.json()
            text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
            usage = data.get("usage") or {}
            return text or "", {
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
            }
    except ModelCallError:
        raise
    except httpx.TimeoutException:
        raise ModelCallError(f"请求超时（{timeout}s）", kind="timeout")
    except httpx.HTTPStatusError as e:
        raise ModelCallError(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        raise ModelCallError(f"请求失败: {e}")


async def _stream_anthropic(cfg: ModelConfig, api_key: str, system: str, user: str,
                            temperature: float, max_tokens: int, timeout: int,
                            on_delta: StreamCallback) -> tuple[str, dict]:
    url = f"{_base_url(cfg)}/v1/messages"
    body = {
        "model": cfg.model_name,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "stream": True,
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    content: list[str] = []
    usage: dict = {}
    event_name = ""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            async with client.stream("POST", url, headers=headers, json=body) as resp:
                if resp.status_code == 429:
                    raise ModelCallError(f"限流 429: {await resp.aread()}", kind="rate_limit")
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("event:"):
                        event_name = line[6:].strip()
                        continue
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if raw == "[DONE]":
                        break
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if event_name == "message_start":
                        usage = data.get("message", {}).get("usage") or usage
                    elif event_name == "message_delta":
                        usage.update(data.get("usage") or {})
                    delta = data.get("delta") or {}
                    text = delta.get("text") if delta.get("type") == "text_delta" else None
                    if text:
                        content.append(text)
                        await on_delta(text)
        return "".join(content), {
            "prompt_tokens": usage.get("input_tokens", usage.get("prompt_tokens", 0)),
            "completion_tokens": usage.get("output_tokens", usage.get("completion_tokens", 0)),
        }
    except ModelCallError:
        raise
    except httpx.TimeoutException:
        raise ModelCallError(f"请求超时（{timeout}s）", kind="timeout")
    except httpx.HTTPStatusError as e:
        raise ModelCallError(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        raise ModelCallError(f"请求失败: {e}")


def parse_ai_json(content: str) -> dict | None:
    """解析模型输出 JSON，带一次格式修复（去除代码围栏/提取花括号块）。"""
    text = content.strip()
    candidates = [text]
    if "```" in text:
        import re
        m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
        if m:
            candidates.append(m.group(1).strip())
    for c in candidates:
        try:
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    # 提取第一个 { 到最后一个 }
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            obj = json.loads(text[start:end + 1])
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    return None


async def test_connection(cfg: ModelConfig, api_key: str) -> dict:
    """后台“测试连接”：发送最小请求，返回延迟与结果。"""
    start = time.monotonic()
    try:
        content, usage = await call_model(
            cfg, api_key,
            system="你是连接测试助手。",
            user="请只回复：连接成功",
            temperature=0, max_tokens=16)
        latency = int((time.monotonic() - start) * 1000)
        if not content.strip():
            return {"ok": False, "latency_ms": latency, "message": "连接成功但模型响应为空"}
        return {"ok": True, "latency_ms": latency, "message": f"连接成功（{latency}ms），响应：{content[:50]}"}
    except ModelCallError as e:
        latency = int((time.monotonic() - start) * 1000)
        return {"ok": False, "latency_ms": latency, "message": f"连接失败：{e.message}"}
