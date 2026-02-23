from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.deps import config_manager

router = APIRouter(prefix="/api/config", tags=["config"])


class APIConfigCreate(BaseModel):
    name: str
    base_url: str
    api_key: str
    model: str
    is_default: bool = False


class APIConfigUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    is_default: Optional[bool] = None


class MinerUConfigCreate(BaseModel):
    name: str
    token: str
    is_default: bool = False


class MinerUConfigUpdate(BaseModel):
    name: Optional[str] = None
    token: Optional[str] = None
    is_default: Optional[bool] = None


class PromptConfigCreate(BaseModel):
    name: str
    prompt: str


class PromptConfigUpdate(BaseModel):
    name: Optional[str] = None
    prompt: Optional[str] = None
    is_enabled: Optional[bool] = None


class ClientConfigResponse(BaseModel):
    max_concurrent_requests: int = 5
    request_timeout: int = 120
    total_request_timeout: int = 300
    cleanup_interval: int = 60
    batch_import_delay: int = 2


class ClientConfigUpdate(BaseModel):
    max_concurrent_requests: Optional[int] = None
    request_timeout: Optional[int] = None
    total_request_timeout: Optional[int] = None
    cleanup_interval: Optional[int] = None
    batch_import_delay: Optional[int] = None


@router.get("/api")
async def get_api_configs():
    configs = config_manager.get_api_configs()
    current_id = config_manager._current_api_id
    return {"configs": [c.model_dump() for c in configs], "current_id": current_id}


@router.post("/api")
async def create_api_config(config: APIConfigCreate):
    new_config = config_manager.add_api_config(
        name=config.name,
        base_url=config.base_url,
        api_key=config.api_key,
        model=config.model,
        is_default=config.is_default,
    )
    return new_config.model_dump()


@router.put("/api/{config_id}")
async def update_api_config(config_id: str, config: APIConfigUpdate):
    updated = config_manager.update_api_config(
        config_id, **{k: v for k, v in config.model_dump().items() if v is not None}
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Config not found")
    return updated.model_dump()


@router.delete("/api/{config_id}")
async def delete_api_config(config_id: str):
    if not config_manager.delete_api_config(config_id):
        raise HTTPException(status_code=404, detail="Config not found")
    return {"status": "deleted"}


@router.post("/api/{config_id}/set-current")
async def set_current_api(config_id: str):
    if not config_manager.set_current_api(config_id):
        raise HTTPException(status_code=404, detail="Config not found")
    return {"status": "ok"}


@router.get("/mineru")
async def get_mineru_configs():
    configs = config_manager.get_mineru_configs()
    current_id = config_manager._current_mineru_id
    return {"configs": [c.model_dump() for c in configs], "current_id": current_id}


@router.post("/mineru")
async def create_mineru_config(config: MinerUConfigCreate):
    new_config = config_manager.add_mineru_config(
        name=config.name, token=config.token, is_default=config.is_default
    )
    return new_config.model_dump()


@router.put("/mineru/{config_id}")
async def update_mineru_config(config_id: str, config: MinerUConfigUpdate):
    updated = config_manager.update_mineru_config(
        config_id, **{k: v for k, v in config.model_dump().items() if v is not None}
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Config not found")
    return updated.model_dump()


@router.delete("/mineru/{config_id}")
async def delete_mineru_config(config_id: str):
    if not config_manager.delete_mineru_config(config_id):
        raise HTTPException(status_code=404, detail="Config not found")
    return {"status": "deleted"}


@router.post("/mineru/{config_id}/set-current")
async def set_current_mineru(config_id: str):
    if not config_manager.set_current_mineru(config_id):
        raise HTTPException(status_code=404, detail="Config not found")
    return {"status": "ok"}


@router.get("/prompts")
async def get_prompt_configs():
    configs = config_manager.get_prompt_configs()
    return [c.model_dump() for c in configs]


@router.post("/prompts")
async def create_prompt_config(config: PromptConfigCreate):
    new_config = config_manager.add_prompt_config(
        name=config.name, prompt=config.prompt
    )
    return new_config.model_dump()


@router.put("/prompts/{config_id}")
async def update_prompt_config(config_id: str, config: PromptConfigUpdate):
    updated = config_manager.update_prompt_config(
        config_id, **{k: v for k, v in config.model_dump().items() if v is not None}
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Config not found")
    return updated.model_dump()


@router.delete("/prompts/{config_id}")
async def delete_prompt_config(config_id: str):
    if not config_manager.delete_prompt_config(config_id):
        raise HTTPException(status_code=404, detail="Config not found")
    return {"status": "deleted"}


@router.post("/client")
async def save_client_config(config: ClientConfigUpdate):
    config_dict = {k: v for k, v in config.model_dump().items() if v is not None}
    updated = config_manager.save_client_config(config_dict)
    return updated
