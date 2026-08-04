"""REST API 冒烟测试：账号、对局、管理员后台。"""
import httpx
import pytest
from unittest.mock import AsyncMock, patch

from app.main import app
from app.game.engine import GameEngine


@pytest.fixture
async def client():
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


async def _register(client, username, password="pass123"):
    r = await client.post("/auth/register", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


async def _login(client, username, password="pass123"):
    r = await client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


async def test_auth_flow(client):
    await _register(client, "alice")
    await _login(client, "alice")
    r = await client.get("/auth/me")
    assert r.json()["user"]["username"] == "alice"
    # 未登录状态
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c2:
        r = await c2.get("/auth/me")
        assert r.json()["user"] is None
    # 重复注册
    r = await client.post("/auth/register", json={"username": "alice", "password": "pass123"})
    assert r.status_code == 409
    # 错误密码
    r = await client.post("/auth/login", json={"username": "alice", "password": "wrong"})
    assert r.status_code == 401
    # 退出
    r = await client.post("/auth/logout")
    assert r.status_code == 200
    r = await client.get("/auth/me")
    assert r.json()["user"] is None


async def test_create_and_second_game_conflict(client):
    # 先准备一个可用模型配置（ai-fill 需要）
    await _login(client, "admin", "admin123")
    r = await client.post("/admin/model-configs", json={
        "display_name": "测试模型",
        "protocol": "openai_compatible",
        "base_url": "https://test.local/v1",
        "model_name": "t",
        "api_key": "sk-x",
        "is_default_fallback": True,
    })
    assert r.status_code == 200, r.text
    await _register(client, "host")
    await _login(client, "host")
    r = await client.post("/game/current", json={"board_size": 6})
    assert r.status_code == 200, r.text
    # 第二个对局 → 409
    r = await client.post("/game/current", json={"board_size": 9})
    assert r.status_code == 409
    # 加入
    r = await client.post("/game/current/join", json={})
    assert r.status_code == 200, r.text
    assert r.json()["seat"] == 1
    # 准备
    r = await client.post("/game/current/ready", json={"ready": True})
    assert r.status_code == 200
    # AI 补齐
    r = await client.post("/game/current/ai-fill", json={})
    assert r.status_code == 200, r.text
    # 开始
    with patch.object(GameEngine, "start_loop", new=AsyncMock()):
        r = await client.post("/game/current/start")
        assert r.status_code == 200, r.text
    r = await client.get("/game/current")
    data = r.json()
    assert data["game"]["status"] == "running"
    assert len(data["players"]) == 6
    assert data["me"]["seat"] == 1
    assert data["me"]["ready"] is True


async def test_join_requires_login(client):
    r = await client.post("/game/current/join", json={})
    assert r.status_code == 401


async def test_admin_model_config_crud(client):
    # 种子管理员
    await _login(client, "admin", "admin123")
    r = await client.get("/admin/model-configs")
    assert r.status_code == 200
    assert r.json()["models"] == []
    # 创建
    r = await client.post("/admin/model-configs", json={
        "display_name": "本地模型",
        "protocol": "openai_compatible",
        "base_url": "https://test.local/v1",
        "model_name": "gpt-test",
        "api_key": "sk-secret-1",
        "is_default_fallback": True,
    })
    assert r.status_code == 200, r.text
    model = r.json()["model"]
    assert model["has_api_key"] is True
    assert "api_key" not in model
    # 列表不返回密钥
    r = await client.get("/admin/model-configs")
    assert "sk-secret-1" not in r.text
    # 测试连接（本地必然失败，但接口正常返回）
    r = await client.post(f"/admin/model-configs/{model['id']}/test")
    assert r.status_code == 200
    assert r.json()["ok"] is False
    # 更新（不提供 key 保留原密钥）
    r = await client.patch(f"/admin/model-configs/{model['id']}", json={
        "display_name": "改名",
        "protocol": "openai_compatible",
        "base_url": "https://test.local/v1",
        "model_name": "gpt-test",
        "api_key": "",
    })
    assert r.status_code == 200
    assert r.json()["model"]["display_name"] == "改名"
    # 删除
    r = await client.delete(f"/admin/model-configs/{model['id']}")
    assert r.status_code == 200


async def test_admin_permission_required(client):
    await _register(client, "bob")
    await _login(client, "bob")
    r = await client.get("/admin/model-configs")
    assert r.status_code == 403


async def test_persona_crud(client):
    await _login(client, "admin", "admin123")
    r = await client.post("/admin/ai-personas", json={
        "name": "激进狼", "speaking_style": "带节奏", "aggression": 5,
    })
    assert r.status_code == 200, r.text
    pid = r.json()["persona"]["id"]
    r = await client.get("/admin/ai-personas")
    assert len(r.json()["personas"]) == 1
    r = await client.patch(f"/admin/ai-personas/{pid}", json={
        "name": "保守狼", "speaking_style": "潜水", "aggression": 2,
    })
    assert r.json()["persona"]["name"] == "保守狼"
    r = await client.delete(f"/admin/ai-personas/{pid}")
    assert r.status_code == 200
