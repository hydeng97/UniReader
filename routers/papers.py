import json
import re
import shutil
import uuid
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Optional

import aiofiles
import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.deps import (
    PAPERS_DIR,
    FILE_SERVER_URL,
    config_manager,
    paper_sessions,
    paper_trees,
    paper_contents,
    save_paper_session,
    load_paper_session,
)
from backend.conversation import ConversationTree
from backend.llm_client import LLMClient
from backend.mineru_client import MinerUClient
from backend.pdf_parser import extract_text_from_bytes

router = APIRouter(prefix="/api/papers", tags=["papers"])


class ExtractFromUrlRequest(BaseModel):
    url: str
    filename: Optional[str] = None


class ExtractUrlLocalRequest(BaseModel):
    paper_id: str
    url: str


class PaperUpdate(BaseModel):
    filename: Optional[str] = None


class ClientConfigResponse(BaseModel):
    max_concurrent_requests: int = 5
    request_timeout: int = 120
    total_request_timeout: int = 300
    cleanup_interval: int = 60
    batch_import_delay: int = 2


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    if len(name) > 100:
        name = name[:100]
    return name or "document"


def rename_pdf_to_title(paper_id: str, title: str) -> str:
    paper_dir = PAPERS_DIR / paper_id
    original_path = paper_dir / "original.pdf"

    if not original_path.exists():
        return "original.pdf"

    safe_title = sanitize_filename(title)
    new_filename = f"{safe_title}.pdf"
    new_path = paper_dir / new_filename

    if new_path.exists() and new_path != original_path:
        base = safe_title
        counter = 1
        while new_path.exists():
            new_filename = f"{base}_{counter}.pdf"
            new_path = paper_dir / new_filename
            counter += 1

    if new_path != original_path:
        shutil.move(str(original_path), str(new_path))

    return new_filename


def get_pdf_path(paper_id: str) -> Optional[Path]:
    paper_dir = PAPERS_DIR / paper_id
    session = paper_sessions.get(paper_id, {})

    if session.get("pdf_filename"):
        pdf_path = paper_dir / session["pdf_filename"]
        if pdf_path.exists():
            return pdf_path

    original_path = paper_dir / "original.pdf"
    if original_path.exists():
        return original_path

    for f in paper_dir.glob("*.pdf"):
        return f

    return None


async def extract_title_from_content(content: str, config_manager) -> Optional[str]:
    if not content:
        return None

    api_config = config_manager.get_current_api()
    if not api_config:
        return None

    lines = content.strip().split("\n")
    first_lines = "\n".join(lines[:10])

    try:
        client = LLMClient(api_config)
        messages = [
            {
                "role": "user",
                "content": f"""请从以下文档前几行内容中提取论文标题。只返回标题文本，不要有任何其他内容。

文档内容：
{first_lines}

标题：""",
            }
        ]

        title = await client.chat_complete(messages)
        title = title.strip().strip('"').strip("'").strip()

        if len(title) > 200:
            title = title[:200]

        await client.close()
        return title if title else None
    except Exception as e:
        print(f"Failed to extract title: {e}")
        return None


@router.get("")
async def list_papers():
    papers = []
    for paper_dir in PAPERS_DIR.iterdir():
        if paper_dir.is_dir():
            session_file = paper_dir / "session.json"
            if session_file.exists():
                with open(session_file, "r", encoding="utf-8") as f:
                    session = json.load(f)
                    papers.append(session)
    return papers


@router.get("/file-server-url")
async def get_file_server_url():
    return {"url": FILE_SERVER_URL}


@router.post("/upload")
async def upload_paper(file: UploadFile = File(...)):
    paper_id = str(uuid.uuid4())[:8]
    paper_dir = PAPERS_DIR / paper_id
    paper_dir.mkdir(parents=True, exist_ok=True)

    content = await file.read()
    filename = file.filename or "document"
    file_ext = filename.lower().split(".")[-1] if "." in filename else ""

    if file_ext == "md" or file_ext == "markdown":
        md_path = paper_dir / "content.md"
        async with aiofiles.open(md_path, "wb") as f:
            await f.write(content)

        markdown_content = content.decode("utf-8")
        paper_contents[paper_id] = markdown_content

        paper_sessions[paper_id] = {
            "id": paper_id,
            "filename": filename,
            "created_at": datetime.now().isoformat(),
            "status": "extracted",
            "source_type": "markdown",
        }
        paper_trees[paper_id] = ConversationTree()
        save_paper_session(paper_id)

        return {"paper_id": paper_id, "filename": filename, "status": "extracted"}
    else:
        pdf_path = paper_dir / "original.pdf"
        async with aiofiles.open(pdf_path, "wb") as f:
            await f.write(content)

        paper_sessions[paper_id] = {
            "id": paper_id,
            "filename": filename,
            "created_at": datetime.now().isoformat(),
            "status": "uploaded",
            "source_type": "pdf",
            "pdf_filename": "original.pdf",
        }
        paper_trees[paper_id] = ConversationTree()
        save_paper_session(paper_id)

        file_url = f"{FILE_SERVER_URL}/{paper_id}/original.pdf"
        return {"paper_id": paper_id, "filename": filename, "file_url": file_url}


@router.post("/extract-url")
async def extract_from_url(request: ExtractFromUrlRequest):
    paper_id = str(uuid.uuid4())[:8]
    paper_dir = PAPERS_DIR / paper_id
    paper_dir.mkdir(parents=True, exist_ok=True)

    filename = request.filename or request.url.split("/")[-1] or "document.pdf"
    file_ext = filename.lower().split(".")[-1] if "." in filename else ""

    if file_ext in ("md", "markdown"):
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(request.url)
            response.raise_for_status()
            markdown_content = response.text

        paper_contents[paper_id] = markdown_content
        paper_sessions[paper_id] = {
            "id": paper_id,
            "filename": filename,
            "created_at": datetime.now().isoformat(),
            "source_url": request.url,
            "status": "extracted",
            "source_type": "markdown",
        }
        paper_trees[paper_id] = ConversationTree()
        save_paper_session(paper_id)

        async def stream_result():
            extracted_title = await extract_title_from_content(
                markdown_content, config_manager
            )
            if extracted_title:
                paper_sessions[paper_id]["filename"] = extracted_title
                save_paper_session(paper_id)
            yield f"data: {json.dumps({'status': 'done', 'paper_id': paper_id, 'filename': paper_sessions[paper_id]['filename'], 'title_extracted': bool(extracted_title)})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(stream_result(), media_type="text/event-stream")

    paper_sessions[paper_id] = {
        "id": paper_id,
        "filename": filename,
        "created_at": datetime.now().isoformat(),
        "source_url": request.url,
        "status": "extracting",
        "source_type": "pdf",
    }
    paper_trees[paper_id] = ConversationTree()
    save_paper_session(paper_id)

    mineru_config = config_manager.get_current_mineru()

    async def stream_extraction():
        yield f"data: {json.dumps({'status': 'started', 'paper_id': paper_id, 'filename': filename})}\n\n"

        pdf_downloaded = False
        if mineru_config:
            yield f"data: {json.dumps({'status': 'downloading_pdf'})}\n\n"
            try:
                async with httpx.AsyncClient(timeout=120.0) as http_client:
                    pdf_response = await http_client.get(request.url)
                    pdf_response.raise_for_status()
                    pdf_path = paper_dir / "original.pdf"
                    async with aiofiles.open(pdf_path, "wb") as f:
                        await f.write(pdf_response.content)
                    pdf_downloaded = True
            except Exception as e:
                yield f"data: {json.dumps({'status': 'warning', 'message': f'PDF下载失败: {str(e)}，继续解析'})}\n\n"

            client = MinerUClient(mineru_config)
            try:
                async for result in client.extract_from_url(request.url):
                    if result["status"] == "created":
                        yield f"data: {json.dumps({'status': 'created', 'task_id': result['task_id']})}\n\n"
                    elif result["status"] == "pending":
                        yield f"data: {json.dumps({'status': 'pending'})}\n\n"
                    elif result["status"] == "running":
                        yield f"data: {json.dumps({'status': 'running', 'progress': result})}\n\n"
                    elif result["status"] == "converting":
                        yield f"data: {json.dumps({'status': 'converting'})}\n\n"
                    elif result["status"] == "done":
                        markdown_content = result.get("markdown", "")
                        paper_contents[paper_id] = markdown_content
                        paper_sessions[paper_id]["status"] = "extracted"
                        save_paper_session(paper_id)

                        extracted_title = await extract_title_from_content(
                            markdown_content, config_manager
                        )
                        if extracted_title:
                            paper_sessions[paper_id]["filename"] = extracted_title
                            pdf_filename = rename_pdf_to_title(
                                paper_id, extracted_title
                            )
                            paper_sessions[paper_id]["pdf_filename"] = pdf_filename
                            save_paper_session(paper_id)

                        yield f"data: {json.dumps({'status': 'done', 'paper_id': paper_id, 'filename': paper_sessions[paper_id]['filename'], 'title_extracted': bool(extracted_title)})}\n\n"
                    elif result["status"] == "error":
                        err_msg = result.get("message", "解析失败")
                        paper_sessions[paper_id]["status"] = "error"
                        paper_sessions[paper_id]["error_message"] = err_msg
                        save_paper_session(paper_id)
                        yield f"data: {json.dumps({'status': 'error', 'message': f'MinerU错误: {err_msg}'})}\n\n"
                        break
            except httpx.HTTPStatusError as e:
                paper_sessions[paper_id]["status"] = "error"
                paper_sessions[paper_id]["error_message"] = (
                    f"HTTP {e.response.status_code}"
                )
                save_paper_session(paper_id)
                yield f"data: {json.dumps({'status': 'error', 'message': f'MinerU API错误: HTTP {e.response.status_code}'})}\n\n"
            except httpx.RequestError as e:
                paper_sessions[paper_id]["status"] = "error"
                paper_sessions[paper_id]["error_message"] = str(e)
                save_paper_session(paper_id)
                yield f"data: {json.dumps({'status': 'error', 'message': f'MinerU连接失败: {type(e).__name__}: {str(e)}'})}\n\n"
            except Exception as e:
                paper_sessions[paper_id]["status"] = "error"
                paper_sessions[paper_id]["error_message"] = str(e)
                save_paper_session(paper_id)
                yield f"data: {json.dumps({'status': 'error', 'message': f'MinerU异常: {type(e).__name__}: {str(e)}'})}\n\n"
            finally:
                await client.close()
        else:
            paper_sessions[paper_id]["status"] = "error"
            paper_sessions[paper_id]["error_message"] = "未配置MinerU"
            save_paper_session(paper_id)
            yield f"data: {json.dumps({'status': 'error', 'message': '未配置MinerU，请配置或使用本地解析'})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(stream_extraction(), media_type="text/event-stream")


@router.post("/extract-url-local")
async def extract_from_url_local(request: ExtractUrlLocalRequest):
    paper_id = request.paper_id

    if paper_id not in paper_sessions:
        if not load_paper_session(paper_id):
            raise HTTPException(status_code=404, detail="Paper not found")

    paper_dir = PAPERS_DIR / paper_id

    async def stream_local_extraction():
        try:
            yield f"data: {json.dumps({'status': 'local', 'message': '正在使用本地解析器...'})}\n\n"
            async with httpx.AsyncClient(timeout=120.0) as http_client:
                response = await http_client.get(request.url)
                response.raise_for_status()
                pdf_bytes = response.content

            pdf_path = paper_dir / "original.pdf"
            async with aiofiles.open(pdf_path, "wb") as f:
                await f.write(pdf_bytes)

            text_content = extract_text_from_bytes(pdf_bytes)
            paper_contents[paper_id] = text_content
            paper_sessions[paper_id]["status"] = "extracted"
            save_paper_session(paper_id)

            extracted_title = await extract_title_from_content(
                text_content, config_manager
            )
            if extracted_title:
                paper_sessions[paper_id]["filename"] = extracted_title
                pdf_filename = rename_pdf_to_title(paper_id, extracted_title)
                paper_sessions[paper_id]["pdf_filename"] = pdf_filename
                save_paper_session(paper_id)

            yield f"data: {json.dumps({'status': 'done', 'filename': paper_sessions[paper_id]['filename'], 'title_extracted': bool(extracted_title)})}\n\n"
        except Exception as e:
            paper_sessions[paper_id]["status"] = "error"
            paper_sessions[paper_id]["error_message"] = str(e)
            save_paper_session(paper_id)
            yield f"data: {json.dumps({'status': 'error', 'message': f'本地解析失败: {str(e)}'})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(stream_local_extraction(), media_type="text/event-stream")


@router.get("/{paper_id}/extract")
async def extract_paper(paper_id: str, file_server_url: str):
    if paper_id not in paper_sessions:
        if not load_paper_session(paper_id):
            raise HTTPException(status_code=404, detail="Paper not found")

    paper_dir = PAPERS_DIR / paper_id
    pdf_path = get_pdf_path(paper_id)

    if not pdf_path:
        raise HTTPException(status_code=400, detail="PDF file not found")

    mineru_config = config_manager.get_current_mineru()
    file_url = f"{file_server_url}/{paper_id}/{pdf_path.name}"

    async def stream_extraction():
        is_local_file = file_server_url and (
            file_server_url.startswith("http://127.")
            or file_server_url.startswith("http://192.168.")
            or file_server_url.startswith("http://10.")
            or file_server_url.startswith("http://172.")
        )

        if is_local_file:
            yield f"data: {json.dumps({'status': 'error', 'message': '本地上传的文件无法被MinerU公网服务访问，请点击使用本地解析按钮'})}\n\n"
        elif mineru_config:
            client = MinerUClient(mineru_config)
            try:
                async for result in client.extract_from_url(file_url):
                    if result["status"] == "created":
                        yield f"data: {json.dumps({'status': 'created', 'task_id': result['task_id']})}\n\n"
                    elif result["status"] == "pending":
                        yield f"data: {json.dumps({'status': 'pending'})}\n\n"
                    elif result["status"] == "running":
                        yield f"data: {json.dumps({'status': 'running', 'progress': result})}\n\n"
                    elif result["status"] == "converting":
                        yield f"data: {json.dumps({'status': 'converting'})}\n\n"
                    elif result["status"] == "done":
                        markdown_content = result.get("markdown", "")
                        paper_contents[paper_id] = markdown_content
                        paper_sessions[paper_id]["status"] = "extracted"
                        save_paper_session(paper_id)

                        extracted_title = await extract_title_from_content(
                            markdown_content, config_manager
                        )
                        if extracted_title:
                            paper_sessions[paper_id]["filename"] = extracted_title
                            pdf_filename = rename_pdf_to_title(
                                paper_id, extracted_title
                            )
                            paper_sessions[paper_id]["pdf_filename"] = pdf_filename
                            save_paper_session(paper_id)

                        yield f"data: {json.dumps({'status': 'done', 'filename': paper_sessions[paper_id]['filename'], 'title_extracted': bool(extracted_title)})}\n\n"
                    elif result["status"] == "error":
                        err_msg = result.get("message", "解析失败")
                        yield f"data: {json.dumps({'status': 'error', 'message': f'MinerU错误: {err_msg}'})}\n\n"
                        break
            except httpx.HTTPStatusError as e:
                yield f"data: {json.dumps({'status': 'error', 'message': f'MinerU API错误: HTTP {e.response.status_code}'})}\n\n"
            except httpx.RequestError as e:
                yield f"data: {json.dumps({'status': 'error', 'message': f'MinerU连接失败: {type(e).__name__}: {str(e)}'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'status': 'error', 'message': f'MinerU异常: {type(e).__name__}: {str(e)}'})}\n\n"
            finally:
                await client.close()
        else:
            yield f"data: {json.dumps({'status': 'error', 'message': '未配置MinerU，请点击使用本地解析按钮'})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(stream_extraction(), media_type="text/event-stream")


@router.get("/{paper_id}/extract-local")
async def extract_paper_local(paper_id: str):
    if paper_id not in paper_sessions:
        if not load_paper_session(paper_id):
            raise HTTPException(status_code=404, detail="Paper not found")

    paper_dir = PAPERS_DIR / paper_id
    pdf_path = get_pdf_path(paper_id)

    if not pdf_path:
        raise HTTPException(status_code=400, detail="PDF file not found")

    async def stream_local_extraction():
        try:
            yield f"data: {json.dumps({'status': 'local', 'message': '正在使用本地解析器...'})}\n\n"
            async with aiofiles.open(pdf_path, "rb") as f:
                pdf_bytes = await f.read()

            text_content = extract_text_from_bytes(pdf_bytes)
            paper_contents[paper_id] = text_content
            paper_sessions[paper_id]["status"] = "extracted"
            save_paper_session(paper_id)

            extracted_title = await extract_title_from_content(
                text_content, config_manager
            )
            if extracted_title:
                paper_sessions[paper_id]["filename"] = extracted_title
                pdf_filename = rename_pdf_to_title(paper_id, extracted_title)
                paper_sessions[paper_id]["pdf_filename"] = pdf_filename
                save_paper_session(paper_id)

            yield f"data: {json.dumps({'status': 'done', 'filename': paper_sessions[paper_id]['filename'], 'title_extracted': bool(extracted_title)})}\n\n"
        except Exception as e:
            paper_sessions[paper_id]["status"] = "error"
            paper_sessions[paper_id]["error_message"] = str(e)
            save_paper_session(paper_id)
            yield f"data: {json.dumps({'status': 'error', 'message': f'本地解析失败: {str(e)}'})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(stream_local_extraction(), media_type="text/event-stream")


@router.get("/{paper_id}")
async def get_paper(paper_id: str):
    if paper_id not in paper_sessions:
        if not load_paper_session(paper_id):
            raise HTTPException(status_code=404, detail="Paper not found")

    return paper_sessions[paper_id]


@router.delete("/{paper_id}")
async def delete_paper(paper_id: str):
    paper_dir = PAPERS_DIR / paper_id
    if paper_dir.exists():
        shutil.rmtree(paper_dir)

    paper_sessions.pop(paper_id, None)
    paper_trees.pop(paper_id, None)
    paper_contents.pop(paper_id, None)

    return {"status": "deleted"}


@router.put("/{paper_id}")
async def update_paper(paper_id: str, update: PaperUpdate):
    if paper_id not in paper_sessions:
        if not load_paper_session(paper_id):
            raise HTTPException(status_code=404, detail="Paper not found")

    if update.filename:
        paper_sessions[paper_id]["filename"] = update.filename
        save_paper_session(paper_id)

    return paper_sessions[paper_id]


@router.get("/{paper_id}/content")
async def get_paper_content(paper_id: str):
    if paper_id not in paper_contents:
        if not load_paper_session(paper_id):
            raise HTTPException(status_code=404, detail="Paper not found")

    return {"content": paper_contents.get(paper_id, "")}
