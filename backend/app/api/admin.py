"""管理员后台：模型配置与 AI 人格。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from ..database import SessionLocal
from ..models import AIPersona, ModelConfig, User
from ..schemas import ModelConfigIn, PersonaIn
from ..security import decrypt_secret, encrypt_secret
from ..ai.adapters import test_connection
from .deps import require_admin, require_user

router = APIRouter(prefix="/admin", tags=["admin"])


def model_dict(m: ModelConfig) -> dict:
    return {
        "id": m.id,
        "display_name": m.display_name,
        "protocol": m.protocol,
        "base_url": m.base_url,
        "model_name": m.model_name,
        "temperature": m.temperature,
        "max_output_tokens": m.max_output_tokens,
        "timeout_seconds": m.timeout_seconds,
        "enabled": m.enabled,
        "is_default_fallback": m.is_default_fallback,
        "has_api_key": bool(m.encrypted_api_key),
    }


@router.get("/model-configs")
async def list_models(_: User = Depends(require_user)):
    """已登录用户可读（大厅选模型需要）；写操作仅管理员。"""
    async with SessionLocal() as db:
        rows = (await db.execute(select(ModelConfig).order_by(ModelConfig.id))).scalars().all()
        return {"models": [model_dict(m) for m in rows]}


@router.post("/model-configs")
async def create_model(body: ModelConfigIn, _: User = Depends(require_admin)):
    if not body.api_key:
        raise HTTPException(status_code=400, detail="必须提供 API Key")
    async with SessionLocal() as db:
        m = ModelConfig(
            display_name=body.display_name,
            protocol=body.protocol,
            base_url=body.base_url,
            model_name=body.model_name,
            encrypted_api_key=encrypt_secret(body.api_key),
            temperature=body.temperature,
            max_output_tokens=body.max_output_tokens,
            timeout_seconds=body.timeout_seconds,
            enabled=body.enabled,
            is_default_fallback=body.is_default_fallback,
        )
        if body.is_default_fallback:
            for other in (await db.execute(select(ModelConfig))).scalars().all():
                other.is_default_fallback = False
        db.add(m)
        await db.commit()
        await db.refresh(m)
        return {"ok": True, "model": model_dict(m)}


@router.patch("/model-configs/{model_id}")
async def update_model(model_id: int, body: ModelConfigIn, _: User = Depends(require_admin)):
    async with SessionLocal() as db:
        m = await db.get(ModelConfig, model_id)
        if m is None:
            raise HTTPException(status_code=404, detail="模型配置不存在")
        m.display_name = body.display_name
        m.protocol = body.protocol
        m.base_url = body.base_url
        m.model_name = body.model_name
        if body.api_key:
            m.encrypted_api_key = encrypt_secret(body.api_key)
        m.temperature = body.temperature
        m.max_output_tokens = body.max_output_tokens
        m.timeout_seconds = body.timeout_seconds
        m.enabled = body.enabled
        if body.is_default_fallback:
            for other in (await db.execute(select(ModelConfig))).scalars().all():
                if other.id != model_id:
                    other.is_default_fallback = False
        m.is_default_fallback = body.is_default_fallback
        await db.commit()
        return {"ok": True, "model": model_dict(m)}


@router.delete("/model-configs/{model_id}")
async def delete_model(model_id: int, _: User = Depends(require_admin)):
    async with SessionLocal() as db:
        m = await db.get(ModelConfig, model_id)
        if m is None:
            raise HTTPException(status_code=404, detail="模型配置不存在")
        await db.delete(m)
        await db.commit()
    return {"ok": True}


@router.post("/model-configs/{model_id}/test")
async def test_model(model_id: int, _: User = Depends(require_admin)):
    async with SessionLocal() as db:
        m = await db.get(ModelConfig, model_id)
        if m is None:
            raise HTTPException(status_code=404, detail="模型配置不存在")
        api_key = decrypt_secret(m.encrypted_api_key)
    result = await test_connection(m, api_key)
    return result


def persona_dict(p: AIPersona) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "speaking_style": p.speaking_style,
        "risk_preference": p.risk_preference,
        "reasoning_style": p.reasoning_style,
        "aggression": p.aggression,
        "description": p.description,
    }


@router.get("/ai-personas")
async def list_personas(_: User = Depends(require_user)):
    """已登录用户可读（大厅选人格需要）；写操作仅管理员。"""
    async with SessionLocal() as db:
        rows = (await db.execute(select(AIPersona).order_by(AIPersona.id))).scalars().all()
        return {"personas": [persona_dict(p) for p in rows]}


@router.post("/ai-personas")
async def create_persona(body: PersonaIn, _: User = Depends(require_admin)):
    async with SessionLocal() as db:
        p = AIPersona(**body.model_dump())
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return {"ok": True, "persona": persona_dict(p)}


@router.patch("/ai-personas/{persona_id}")
async def update_persona(persona_id: int, body: PersonaIn, _: User = Depends(require_admin)):
    async with SessionLocal() as db:
        p = await db.get(AIPersona, persona_id)
        if p is None:
            raise HTTPException(status_code=404, detail="人格不存在")
        for k, v in body.model_dump().items():
            setattr(p, k, v)
        await db.commit()
        return {"ok": True, "persona": persona_dict(p)}


@router.delete("/ai-personas/{persona_id}")
async def delete_persona(persona_id: int, _: User = Depends(require_admin)):
    async with SessionLocal() as db:
        p = await db.get(AIPersona, persona_id)
        if p is None:
            raise HTTPException(status_code=404, detail="人格不存在")
        await db.delete(p)
        await db.commit()
    return {"ok": True}
