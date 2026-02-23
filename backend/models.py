from __future__ import annotations
from pydantic import BaseModel
from typing import Optional, List


class Message(BaseModel):
    id: str
    role: str
    content: str
    timestamp: str
    parent_id: Optional[str] = None
    branch_name: Optional[str] = None
    is_initial: bool = False
    prompt_name: Optional[str] = None
    model_name: Optional[str] = None
    context_tokens: Optional[int] = None


class ConversationBranch(BaseModel):
    id: str
    name: str
    messages: List[Message]
    created_at: str
    with_context: bool = True


class PaperSession(BaseModel):
    id: str
    filename: str
    text_content: str
    branches: List[ConversationBranch]
    created_at: str
    current_branch_id: Optional[str] = None


class APIConfig(BaseModel):
    id: str
    name: str
    base_url: str
    api_key: str
    model: str
    is_default: bool = False


class PromptConfig(BaseModel):
    id: str
    name: str
    prompt: str
    is_enabled: bool = True


class MinerUConfig(BaseModel):
    id: str
    name: str
    token: str
    is_default: bool = False
