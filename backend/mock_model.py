"""本地 Mock OpenAI 兼容模型服务：用于无真实 API Key 时的端到端联调。

用法：../.venv/Scripts/python mock_model.py   （监听 127.0.0.1:8899）
在后台添加模型配置：base_url=http://127.0.0.1:8899/v1，protocol=openai_compatible
"""
import json
import re
import asyncio
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

app = FastAPI()


def extract_targets(text: str) -> list[int]:
    """从提示词“合法目标：”行提取座位号。"""
    m = re.search(r"合法目标：([^\n]*)", text)
    if not m:
        return []
    return [int(x) for x in re.findall(r"(\d+)号", m.group(1))]


def decide(prompt: str) -> dict:
    m = re.search(r"窗口：(\S+)", prompt)
    window = m.group(1) if m else ""

    if window == "上警":
        return {"action_type": "apply"}
    if window == "狼人杀人":
        targets = extract_targets(prompt)
        return {"action_type": "wolf_kill", "target_seat_number": targets[0]} if targets else {"action_type": "pass"}
    if window == "狼人私聊":
        return {"action_type": "chat", "chat_message": "先听完队友判断，再统一选择最稳妥的目标。"}
    if window == "猎人开枪":
        targets = extract_targets(prompt)
        return {"action_type": "shoot", "target_seat_number": targets[0]} if targets else {"action_type": "pass"}
    if window == "警徽移交":
        targets = extract_targets(prompt)
        return {"action_type": "transfer", "target_seat_number": targets[0]} if targets else {"action_type": "destroy"}
    if window == "夜间技能":
        if "守护目标" in prompt:
            targets = extract_targets(prompt)
            return {"action_type": "protect", "target_seat_number": targets[0]} if targets else {"action_type": "pass"}
        if "查验目标" in prompt:
            targets = extract_targets(prompt)
            return {"action_type": "check", "target_seat_number": targets[0]} if targets else {"action_type": "pass"}
        if "使用解药" in prompt:
            m2 = re.search(r"💊 救 (\d+)号", prompt)
            if m2:
                return {"action_type": "save", "target_seat_number": int(m2.group(1))}
        if "使用毒药" in prompt:
            m2 = re.search(r"☠️ 毒 (\d+)号", prompt)
            if m2:
                return {"action_type": "poison", "target_seat_number": int(m2.group(1))}
        return {"action_type": "pass"}
    if "投票" in window:
        targets = extract_targets(prompt)
        return {"action_type": "vote", "target_seat_number": targets[0]} if targets else {"action_type": "vote", "target_seat_number": 0}
    if "发言" in window or window == "遗言":
        m2 = re.search(r"坐在 (\d+) 号位", prompt)
        seat = m2.group(1) if m2 else "?"
        return {"action_type": "speak", "speech": f"我是{seat}号，先表个态：我是好人，大家别投我。"}
    return {"action_type": "pass"}


@app.post("/v1/chat/completions")
async def chat(request: Request):
    body = await request.json()
    prompt = ""
    for msg in body.get("messages", []):
        prompt += msg.get("content", "") + "\n"
    result = decide(prompt)
    content = json.dumps(result, ensure_ascii=False)
    if body.get("stream"):
        async def event_stream():
            for index in range(0, len(content), 8):
                piece = content[index:index + 8]
                chunk = {"choices": [{"index": 0, "delta": {"content": piece}}]}
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.02)
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")
    return JSONResponse({
        "id": "mock-" + str(datetime.now().timestamp()),
        "object": "chat.completion",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 30},
    })


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8899, log_level="warning")
