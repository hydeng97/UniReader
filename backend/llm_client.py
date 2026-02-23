from __future__ import annotations
import json
import httpx
import asyncio
import re
from typing import AsyncGenerator, Optional, List, Dict, Tuple
from backend.models import APIConfig


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    other_chars = len(text) - chinese_chars
    return int(chinese_chars * 1.5 + other_chars / 4)


def estimate_messages_tokens(
    messages: List[Dict], system_prompt: Optional[str] = None
) -> int:
    total = 0
    if system_prompt:
        total += estimate_tokens(system_prompt)
    for msg in messages:
        total += estimate_tokens(msg.get("content", ""))
        total += 4
    return total


class LLMClient:
    def __init__(self, config: APIConfig):
        self.config = config
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client

    async def chat_stream(
        self, messages: List[Dict], system_prompt: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        payload = {
            "model": self.config.model,
            "messages": full_messages,
            "stream": True,
        }

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self.config.base_url.rstrip('/')}/chat/completions"

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                async with client.stream(
                    "POST", url, json=payload, headers=headers
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data)
                                if "choices" in chunk and len(chunk["choices"]) > 0:
                                    delta = chunk["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue
            except httpx.ConnectError as e:
                raise Exception(
                    f"无法连接到 LLM API 服务器 ({self.config.base_url})，请检查网络连接或 VPN 设置"
                )
            except httpx.TimeoutException:
                raise Exception(f"LLM API 请求超时，请检查网络连接")
            except httpx.HTTPStatusError as e:
                raise Exception(f"LLM API 返回错误: HTTP {e.response.status_code}")
            except OSError as e:
                if "nodename" in str(e) or "servname" in str(e):
                    raise Exception(
                        f"DNS 解析失败 ({self.config.base_url})，请检查网络连接或 VPN 设置"
                    )
                raise Exception(f"网络错误: {str(e)}")
            except Exception as e:
                raise Exception(f"LLM API 请求失败: {str(e)}")

    async def chat_complete(
        self, messages: List[Dict], system_prompt: Optional[str] = None
    ) -> str:
        full_content = ""
        async for chunk in self.chat_stream(messages, system_prompt):
            full_content += chunk
        return full_content

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


def analyze_paper_stream(
    client: LLMClient, paper_content: str, prompt: str
) -> Tuple[AsyncGenerator[str, None], int]:
    messages = [
        {"role": "user", "content": f"{prompt}\n\n论文内容如下：\n\n{paper_content}"}
    ]
    tokens = estimate_messages_tokens(messages)
    return client.chat_stream(messages), tokens


def ask_question_stream(
    client: LLMClient,
    paper_content: str,
    conversation_history: List[Dict],
    question: str,
    with_context: bool = True,
) -> Tuple[AsyncGenerator[str, None], int]:
    if with_context:
        system_prompt = f"""你是一个专业的学术论文助手。用户正在阅读一篇论文，并就论文内容向你提问。
以下是论文的完整内容：

{paper_content}

请基于论文内容回答用户的问题。回答要准确、专业，并在必要时引用论文中的具体内容。"""
    else:
        system_prompt = "你是一个专业的学术助手。请根据用户的对话历史回答问题。"

    messages = conversation_history.copy()
    messages.append({"role": "user", "content": question})
    tokens = estimate_messages_tokens(messages, system_prompt)
    return client.chat_stream(messages, system_prompt), tokens


def summarize_conversation_stream(
    client: LLMClient, conversation_content: str
) -> Tuple[AsyncGenerator[str, None], int]:
    system_prompt = (
        "你是一个专业的学术助手。请对以下对话内容进行总结，提取关键信息和要点。"
    )
    messages = [
        {"role": "user", "content": f"请总结以下对话内容：\n\n{conversation_content}"}
    ]
    tokens = estimate_messages_tokens(messages, system_prompt)
    return client.chat_stream(messages, system_prompt), tokens
