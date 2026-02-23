import asyncio
import httpx
import zipfile
import io
import json
from typing import Optional, AsyncGenerator
from backend.models import MinerUConfig

MINERU_API_BASE = "https://mineru.net/api/v4"


class MinerUClient:
    def __init__(self, config: MinerUConfig):
        self.config = config
        self.client = httpx.AsyncClient(timeout=300.0)

    async def create_task(
        self,
        file_url: str,
        model_version: str = "vlm",
        enable_formula: bool = True,
        enable_table: bool = True,
        is_ocr: bool = False,
        language: str = "ch",
    ) -> dict:
        url = f"{MINERU_API_BASE}/extract/task"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.token}",
        }
        data = {
            "url": file_url,
            "model_version": model_version,
            "enable_formula": enable_formula,
            "enable_table": enable_table,
            "is_ocr": is_ocr,
            "language": language,
        }

        try:
            response = await self.client.post(url, headers=headers, json=data)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            return {
                "code": -1,
                "msg": f"HTTP错误: {e.response.status_code} - {e.response.text[:200] if e.response.text else ''}",
            }
        except httpx.RequestError as e:
            return {
                "code": -1,
                "msg": f"连接失败: {str(e) or type(e).__name__}",
            }

    async def get_task_result(self, task_id: str) -> dict:
        url = f"{MINERU_API_BASE}/extract/task/{task_id}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.token}",
        }
        try:
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise Exception(f"查询任务状态失败: HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            raise Exception(f"查询任务状态连接失败: {str(e) or type(e).__name__}")

    async def wait_for_task(
        self,
        task_id: str,
        poll_interval: float = 3.0,
        max_wait: float = 600.0,
    ) -> AsyncGenerator[dict, None]:
        elapsed = 0.0
        while elapsed < max_wait:
            result = await self.get_task_result(task_id)
            yield result

            data = result.get("data", {})
            state = data.get("state", "")

            if state in ("done", "failed"):
                break

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

    async def get_extracted_content(self, zip_url: str) -> dict:
        async with httpx.AsyncClient(
            timeout=60.0, follow_redirects=True
        ) as download_client:
            try:
                response = await download_client.get(zip_url)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise Exception(f"下载ZIP失败: HTTP {e.response.status_code}")
            except httpx.ConnectError as e:
                raise Exception(
                    f"下载ZIP连接失败: 无法连接到CDN服务器，请检查网络或VPN设置"
                )
            except httpx.TimeoutException as e:
                raise Exception(f"下载ZIP超时: 网络连接不稳定")
            except httpx.RequestError as e:
                raise Exception(f"下载ZIP网络错误: {type(e).__name__}: {str(e)}")
            except Exception as e:
                raise Exception(f"下载ZIP异常: {type(e).__name__}: {str(e)}")

        content = {}
        try:
            with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                for name in zf.namelist():
                    if name.endswith(".md"):
                        content["markdown"] = zf.read(name).decode("utf-8")
                    elif name.endswith(".json") and "content_list" in name:
                        try:
                            content["content_list"] = json.loads(
                                zf.read(name).decode("utf-8")
                            )
                        except:
                            pass
                    elif name.endswith(".json") and "layout" in name:
                        try:
                            content["layout"] = json.loads(
                                zf.read(name).decode("utf-8")
                            )
                        except:
                            pass
        except zipfile.BadZipFile:
            raise Exception("下载的文件不是有效的ZIP格式")
        except Exception as e:
            raise Exception(f"解析ZIP失败: {str(e)}")

        return content

    async def extract_from_url(
        self,
        file_url: str,
        model_version: str = "vlm",
        enable_formula: bool = True,
        enable_table: bool = True,
        is_ocr: bool = False,
        language: str = "ch",
    ) -> AsyncGenerator[dict, None]:
        task_result = await self.create_task(
            file_url=file_url,
            model_version=model_version,
            enable_formula=enable_formula,
            enable_table=enable_table,
            is_ocr=is_ocr,
            language=language,
        )

        if task_result.get("code") != 0:
            yield {
                "status": "error",
                "message": task_result.get("msg", "Unknown error"),
            }
            return

        task_id = task_result["data"]["task_id"]
        yield {"status": "created", "task_id": task_id}

        async for result in self.wait_for_task(task_id):
            data = result.get("data", {})
            state = data.get("state", "")

            if state == "done":
                zip_url = data.get("full_zip_url", "")
                if zip_url:
                    content = await self.get_extracted_content(zip_url)
                    yield {
                        "status": "done",
                        "markdown": content.get("markdown", ""),
                        "content_list": content.get("content_list"),
                        "layout": content.get("layout"),
                    }
                else:
                    yield {"status": "error", "message": "No download URL returned"}
                break
            elif state == "failed":
                yield {"status": "error", "message": data.get("err_msg", "Task failed")}
                break
            elif state == "running":
                progress = data.get("extract_progress", {})
                yield {
                    "status": "running",
                    "extracted_pages": progress.get("extracted_pages", 0),
                    "total_pages": progress.get("total_pages", 0),
                }
            elif state == "pending":
                yield {"status": "pending"}
            elif state == "converting":
                yield {"status": "converting"}

    async def close(self):
        await self.client.aclose()
