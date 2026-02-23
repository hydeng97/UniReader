import asyncio
import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.deps import (
    config_manager,
    get_paper_tree,
    get_paper_content,
    save_paper_session,
    load_paper_session,
    paper_contents,
    paper_trees,
)
from backend.models import Message
from backend.llm_client import (
    LLMClient,
    analyze_paper_stream,
    ask_question_stream,
    summarize_conversation_stream,
    estimate_tokens,
)

router = APIRouter(prefix="/api/papers", tags=["chat"])


class QuestionRequest(BaseModel):
    paper_id: str
    branch_id: str
    question: str
    parent_message_id: Optional[str] = None


class SummarizeRequest(BaseModel):
    paper_id: str
    branch_id: Optional[str] = None
    all_branches: bool = False


class RegenerateRequest(BaseModel):
    paper_id: str
    branch_id: str
    message_id: str
    new_question: str


@router.get("/{paper_id}/analyze")
async def analyze_paper(paper_id: str):
    if paper_id not in paper_contents:
        if not load_paper_session(paper_id):
            raise HTTPException(status_code=404, detail="Paper not found")

    api_config = config_manager.get_current_api()
    if not api_config:
        raise HTTPException(status_code=400, detail="No API configuration found")

    prompts = config_manager.get_prompt_configs(enabled_only=True)
    if not prompts:
        raise HTTPException(status_code=400, detail="No enabled prompts found")

    paper_content = paper_contents[paper_id]
    tree = paper_trees[paper_id]
    queue = asyncio.Queue()
    streaming_messages = {}

    async def analyze_single(prompt_config):
        client = LLMClient(api_config)
        branch = tree.create_branch(prompt_config.name)
        save_paper_session(paper_id)

        stream, context_tokens = analyze_paper_stream(
            client, paper_content, prompt_config.prompt
        )

        message = Message(
            id=str(uuid.uuid4())[:8],
            role="assistant",
            content="",
            timestamp=datetime.now().isoformat(),
            is_initial=True,
            prompt_name=prompt_config.name,
            model_name=api_config.model,
            context_tokens=context_tokens,
        )
        tree.add_message_to_branch(branch.id, message)
        streaming_messages[branch.id] = message
        save_paper_session(paper_id)

        await queue.put(
            {
                "branch_id": branch.id,
                "prompt_name": prompt_config.name,
                "status": "starting",
                "model_name": api_config.model,
            }
        )

        result_content = ""
        chunk_count = 0
        try:
            async for chunk in stream:
                result_content += chunk
                message.content = result_content
                chunk_count += 1

                if chunk_count % 10 == 0:
                    save_paper_session(paper_id)

                await queue.put(
                    {
                        "branch_id": branch.id,
                        "prompt_name": prompt_config.name,
                        "chunk": chunk,
                    }
                )

            message.content = result_content
            save_paper_session(paper_id)
            await queue.put(
                {"branch_id": branch.id, "done": True, "message": message.model_dump()}
            )
        except Exception as e:
            await queue.put(
                {
                    "branch_id": branch.id,
                    "prompt_name": prompt_config.name,
                    "error": str(e),
                }
            )
        finally:
            await client.close()

    async def stream_analysis():
        tasks = [asyncio.create_task(analyze_single(p)) for p in prompts]

        completed = 0
        while completed < len(prompts):
            try:
                data = await asyncio.wait_for(queue.get(), timeout=300.0)
                if "error" in data and "branch_id" in data:
                    completed += 1
                elif data.get("done"):
                    completed += 1
                yield f"data: {json.dumps(data)}\n\n"
                await asyncio.sleep(0)
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'error': 'timeout'})}\n\n"
                break

        for task in tasks:
            if not task.done():
                task.cancel()

        save_paper_session(paper_id)
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream_analysis(), media_type="text/event-stream")


@router.post("/{paper_id}/ask")
async def ask_question_endpoint(request: QuestionRequest):
    paper_id = request.paper_id

    if paper_id not in paper_contents:
        if not load_paper_session(paper_id):
            raise HTTPException(status_code=404, detail="Paper not found")

    api_config = config_manager.get_current_api()
    if not api_config:
        raise HTTPException(status_code=400, detail="No API configuration found")

    paper_content = paper_contents[paper_id]
    tree = paper_trees[paper_id]

    branch_id = request.branch_id
    branch = tree.get_branch(branch_id)

    if not branch:
        new_branch = tree.create_branch("问答分支")
        branch_id = new_branch.id
        branch = new_branch

    user_message = Message(
        id=str(uuid.uuid4())[:8],
        role="user",
        content=request.question,
        timestamp=datetime.now().isoformat(),
        parent_id=request.parent_message_id,
    )
    tree.add_message_to_branch(branch_id, user_message)
    save_paper_session(paper_id)

    conversation_history = []
    messages = list(branch.messages)
    i = 0

    while i < len(messages):
        msg = messages[i]
        if msg.role == "system":
            conversation_history.append({"role": "system", "content": msg.content})
            i += 1
        elif msg.role == "user":
            if (
                i + 1 < len(messages)
                and messages[i + 1].role == "assistant"
                and messages[i + 1].content
            ):
                conversation_history.append({"role": "user", "content": msg.content})
                conversation_history.append(
                    {"role": "assistant", "content": messages[i + 1].content}
                )
                i += 2
            else:
                i += 1
        elif msg.role == "assistant" and msg.content:
            conversation_history.append({"role": "assistant", "content": msg.content})
            i += 1
        else:
            i += 1

    async def stream_response():
        client = LLMClient(api_config)
        result_content = ""
        stream, context_tokens = ask_question_stream(
            client,
            paper_content,
            conversation_history,
            request.question,
            with_context=getattr(branch, "with_context", True),
        )

        assistant_message = Message(
            id=str(uuid.uuid4())[:8],
            role="assistant",
            content="",
            timestamp=datetime.now().isoformat(),
            parent_id=user_message.id,
            model_name=api_config.model,
        )
        tree.add_message_to_branch(branch_id, assistant_message)

        yield f"data: {json.dumps({'status': 'started', 'user_msg_id': user_message.id, 'user_msg': user_message.model_dump(), 'assistant_msg_id': assistant_message.id, 'branch_id': branch_id, 'model_name': api_config.model})}\n\n"

        try:
            async for chunk in stream:
                result_content += chunk
                assistant_message.content = result_content
                yield f"data: {json.dumps({'chunk': chunk, 'user_msg_id': user_message.id})}\n\n"

            assistant_message.content = result_content
            assistant_message.context_tokens = context_tokens

            save_paper_session(paper_id)

            yield f"data: {json.dumps({'done': True, 'message': assistant_message.model_dump(), 'branch_id': branch_id, 'user_msg_id': user_message.id})}\n\n"
        except Exception as e:
            assistant_message.content = "错误: " + str(e)
            save_paper_session(paper_id)
            yield f"data: {json.dumps({'error': str(e), 'user_msg_id': user_message.id})}\n\n"
        finally:
            await client.close()
            yield "data: [DONE]\n\n"

    return StreamingResponse(stream_response(), media_type="text/event-stream")


@router.post("/{paper_id}/summarize")
async def summarize_conversations(request: SummarizeRequest):
    paper_id = request.paper_id

    if paper_id not in paper_trees:
        if not load_paper_session(paper_id):
            raise HTTPException(status_code=404, detail="Paper not found")

    api_config = config_manager.get_current_api()
    if not api_config:
        raise HTTPException(status_code=400, detail="No API configuration found")

    tree = paper_trees[paper_id]

    if request.all_branches:
        target_branch_id = request.branch_id or tree.root_branch_id
    else:
        target_branch_id = request.branch_id

    if not target_branch_id:
        new_branch = tree.create_branch("总结")
        target_branch_id = new_branch.id

    branch = tree.get_branch(target_branch_id)
    if not branch:
        new_branch = tree.create_branch("总结")
        target_branch_id = new_branch.id
        branch = new_branch

    if request.all_branches:
        all_content = ""
        for b in tree.get_all_branches():
            all_content += f"\n\n=== 分支: {b.name} ===\n\n"
            for msg in b.messages:
                role_name = "用户" if msg.role == "user" else "AI"
                all_content += f"{role_name}: {msg.content}\n\n"
        conversation_content = all_content
    else:
        conversation_content = ""
        for msg in branch.messages:
            role_name = "用户" if msg.role == "user" else "AI"
            conversation_content += f"{role_name}: {msg.content}\n\n"

    context_tokens = estimate_tokens(conversation_content)
    summary_msg_id = f"summary_{uuid.uuid4().hex[:8]}"

    summary_message = Message(
        id=summary_msg_id,
        role="assistant",
        content="",
        timestamp=datetime.now().isoformat(),
        model_name=api_config.model,
    )
    tree.add_message_to_branch(target_branch_id, summary_message)

    async def stream_summary():
        client = LLMClient(api_config)
        stream, tokens = summarize_conversation_stream(client, conversation_content)
        result_content = ""

        yield f"data: {json.dumps({'status': 'started', 'msg_id': summary_msg_id, 'branch_id': target_branch_id, 'model_name': api_config.model, 'context_tokens': tokens})}\n\n"

        try:
            async for chunk in stream:
                result_content += chunk
                summary_message.content = result_content
                yield f"data: {json.dumps({'chunk': chunk, 'msg_id': summary_msg_id})}\n\n"

            summary_message.content = result_content
            summary_message.context_tokens = context_tokens
            save_paper_session(paper_id)

            yield f"data: {json.dumps({'done': True, 'msg_id': summary_msg_id, 'branch_id': target_branch_id, 'message': summary_message.model_dump()})}\n\n"
        except Exception as e:
            summary_message.content = "错误: " + str(e)
            save_paper_session(paper_id)
            yield f"data: {json.dumps({'error': str(e), 'msg_id': summary_msg_id})}\n\n"
        finally:
            await client.close()

    return StreamingResponse(stream_summary(), media_type="text/event-stream")


@router.post("/{paper_id}/regenerate")
async def regenerate_response(request: RegenerateRequest):
    paper_id = request.paper_id

    if paper_id not in paper_contents:
        if not load_paper_session(paper_id):
            raise HTTPException(status_code=404, detail="Paper not found")

    api_config = config_manager.get_current_api()
    if not api_config:
        raise HTTPException(status_code=400, detail="No API configuration found")

    paper_content = paper_contents[paper_id]
    tree = paper_trees[paper_id]

    branch_id = request.branch_id
    branch = tree.get_branch(branch_id)

    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    msg_idx = None
    for i, msg in enumerate(branch.messages):
        if msg.id == request.message_id:
            msg_idx = i
            break

    if msg_idx is None:
        raise HTTPException(status_code=404, detail="Message not found")

    branch.messages[msg_idx].content = request.new_question
    branch.messages[msg_idx].timestamp = datetime.now().isoformat()

    while (
        msg_idx + 1 < len(branch.messages)
        and branch.messages[msg_idx + 1].role == "assistant"
    ):
        del branch.messages[msg_idx + 1]

    assistant_msg_id = str(uuid.uuid4())[:8]
    assistant_message = Message(
        id=assistant_msg_id,
        role="assistant",
        content="",
        timestamp=datetime.now().isoformat(),
        parent_id=request.message_id,
        model_name=api_config.model,
    )
    branch.messages.insert(msg_idx + 1, assistant_message)

    save_paper_session(paper_id)

    conversation_history = []
    messages = list(branch.messages[: msg_idx + 1])
    i = 0

    while i < len(messages):
        msg = messages[i]
        if msg.role == "system":
            conversation_history.append({"role": "system", "content": msg.content})
            i += 1
        elif msg.role == "user":
            if (
                i + 1 < len(messages)
                and messages[i + 1].role == "assistant"
                and messages[i + 1].content
            ):
                conversation_history.append({"role": "user", "content": msg.content})
                conversation_history.append(
                    {"role": "assistant", "content": messages[i + 1].content}
                )
                i += 2
            else:
                i += 1
        elif msg.role == "assistant" and msg.content:
            conversation_history.append({"role": "assistant", "content": msg.content})
            i += 1
        else:
            i += 1

    async def stream_response():
        client = LLMClient(api_config)
        result_content = ""
        stream, context_tokens = ask_question_stream(
            client,
            paper_content,
            conversation_history,
            request.new_question,
            with_context=getattr(branch, "with_context", True),
        )

        yield f"data: {json.dumps({'status': 'started', 'user_msg_id': request.message_id, 'assistant_msg_id': assistant_msg_id, 'branch_id': branch_id, 'model_name': api_config.model})}\n\n"

        try:
            async for chunk in stream:
                result_content += chunk

                for i, msg in enumerate(branch.messages):
                    if msg.id == assistant_msg_id:
                        branch.messages[i].content = result_content
                        break

                yield f"data: {json.dumps({'chunk': chunk, 'user_msg_id': request.message_id})}\n\n"

            for i, msg in enumerate(branch.messages):
                if msg.id == assistant_msg_id:
                    branch.messages[i].content = result_content
                    branch.messages[i].context_tokens = context_tokens
                    break

            save_paper_session(paper_id)

            final_msg = None
            for msg in branch.messages:
                if msg.id == assistant_msg_id:
                    final_msg = msg
                    break

            yield f"data: {json.dumps({'done': True, 'message': final_msg.model_dump() if final_msg else {}, 'branch_id': branch_id, 'user_msg_id': request.message_id})}\n\n"
        except Exception as e:
            for i, msg in enumerate(branch.messages):
                if msg.id == assistant_msg_id:
                    branch.messages[i].content = "错误: " + str(e)
                    break
            save_paper_session(paper_id)
            yield f"data: {json.dumps({'error': str(e), 'user_msg_id': request.message_id})}\n\n"
        finally:
            await client.close()
            yield "data: [DONE]\n\n"

    return StreamingResponse(stream_response(), media_type="text/event-stream")
