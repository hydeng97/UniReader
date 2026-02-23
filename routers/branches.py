import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.deps import (
    STATIC_DIR,
    get_paper_tree,
    get_paper_session,
    get_paper_content,
    save_paper_session,
    paper_trees,
    paper_sessions,
    paper_contents,
    load_paper_session,
)
from backend.models import Message

router = APIRouter(prefix="/api/papers", tags=["branches"])


class CreateBranchRequest(BaseModel):
    name: Optional[str] = None
    with_context: bool = False


@router.get("/{paper_id}/branches")
async def get_branches(paper_id: str):
    tree = get_paper_tree(paper_id)
    if not tree:
        raise HTTPException(status_code=404, detail="Paper not found")

    return [branch.model_dump() for branch in tree.get_all_branches()]


@router.get("/{paper_id}/branches/{branch_id}")
async def get_branch(paper_id: str, branch_id: str):
    tree = get_paper_tree(paper_id)
    if not tree:
        raise HTTPException(status_code=404, detail="Paper not found")

    branch = tree.get_branch(branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    paper = get_paper_session(paper_id)
    return {
        "branch": branch.model_dump(),
        "paper_name": paper.get("filename", "未命名"),
    }


@router.delete("/{paper_id}/branches/{branch_id}")
async def delete_branch(paper_id: str, branch_id: str):
    tree = get_paper_tree(paper_id)
    if not tree:
        raise HTTPException(status_code=404, detail="Paper not found")

    if branch_id not in tree.branches:
        raise HTTPException(status_code=404, detail="Branch not found")

    del tree.branches[branch_id]

    if tree.root_branch_id == branch_id:
        tree.root_branch_id = next(iter(tree.branches), None)

    save_paper_session(paper_id)

    return {"status": "deleted", "remaining": len(tree.branches)}


@router.post("/{paper_id}/new-branch")
async def create_new_branch(
    paper_id: str,
    parent_branch_id: str,
    parent_message_id: str,
    name: Optional[str] = None,
):
    tree = get_paper_tree(paper_id)
    if not tree:
        raise HTTPException(status_code=404, detail="Paper not found")

    new_branch = tree.create_child_branch(parent_branch_id, parent_message_id, name)

    save_paper_session(paper_id)

    return new_branch.model_dump()


@router.post("/{paper_id}/create-branch")
async def create_branch(paper_id: str, request: CreateBranchRequest):
    tree = get_paper_tree(paper_id)
    if not tree:
        raise HTTPException(status_code=404, detail="Paper not found")

    branch_name = request.name or f"分支 {len(tree.branches) + 1}"
    new_branch = tree.create_branch(branch_name)

    new_branch.with_context = request.with_context

    save_paper_session(paper_id)

    return new_branch.model_dump()


def setup_view_route(app):
    @app.get("/view/{paper_id}/{branch_id}")
    async def view_branch(paper_id: str, branch_id: str):
        return FileResponse(STATIC_DIR / "viewer.html")
