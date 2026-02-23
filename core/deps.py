from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from backend.config_manager import ConfigManager
from backend.conversation import ConversationTree
from backend.models import Message
from core.path_utils import get_static_dir, get_papers_dir, ensure_data_dirs

ensure_data_dirs()

config_manager = ConfigManager()

server_config = config_manager.get_server_config()
SERVER_HOST = server_config.get("host", "0.0.0.0")
SERVER_PORT = server_config.get("port", 8000)
FILE_SERVER_PORT = server_config.get("file_server_port", 8765)

PAPERS_DIR = get_papers_dir()
STATIC_DIR = get_static_dir()

paper_sessions: Dict[str, dict] = {}
paper_trees: Dict[str, ConversationTree] = {}
paper_contents: Dict[str, str] = {}

FILE_SERVER_URL: Optional[str] = None


def get_config_manager() -> ConfigManager:
    return config_manager


def get_paper_tree(paper_id: str) -> Optional[ConversationTree]:
    if paper_id not in paper_trees:
        if not load_paper_session(paper_id):
            return None
    return paper_trees.get(paper_id)


def get_paper_content(paper_id: str) -> Optional[str]:
    if paper_id not in paper_contents:
        load_paper_session(paper_id)
    return paper_contents.get(paper_id)


def get_paper_session(paper_id: str) -> dict:
    return paper_sessions.get(paper_id, {})


def save_paper_session(paper_id: str):
    paper_dir = PAPERS_DIR / paper_id
    paper_dir.mkdir(parents=True, exist_ok=True)

    if paper_id in paper_trees:
        tree_data = paper_trees[paper_id].to_dict()
        with open(paper_dir / "conversation.json", "w", encoding="utf-8") as f:
            json.dump(tree_data, f, ensure_ascii=False, indent=2)

    if paper_id in paper_contents:
        with open(paper_dir / "content.md", "w", encoding="utf-8") as f:
            f.write(paper_contents[paper_id])

    session_info = paper_sessions.get(paper_id, {})
    with open(paper_dir / "session.json", "w", encoding="utf-8") as f:
        json.dump(session_info, f, ensure_ascii=False, indent=2)


def load_paper_session(paper_id: str) -> bool:
    paper_dir = PAPERS_DIR / paper_id
    if not paper_dir.exists():
        return False

    try:
        if (paper_dir / "conversation.json").exists():
            with open(paper_dir / "conversation.json", "r", encoding="utf-8") as f:
                tree_data = json.load(f)
                paper_trees[paper_id] = ConversationTree.from_dict(tree_data)
        else:
            paper_trees[paper_id] = ConversationTree()

        if (paper_dir / "content.md").exists():
            with open(paper_dir / "content.md", "r", encoding="utf-8") as f:
                paper_contents[paper_id] = f.read()
        elif (paper_dir / "content.txt").exists():
            with open(paper_dir / "content.txt", "r", encoding="utf-8") as f:
                paper_contents[paper_id] = f.read()

        if (paper_dir / "session.json").exists():
            with open(paper_dir / "session.json", "r", encoding="utf-8") as f:
                paper_sessions[paper_id] = json.load(f)

        return True
    except Exception as e:
        print(f"Error loading paper session: {e}")
        return False


def delete_paper(paper_id: str) -> bool:
    paper_dir = PAPERS_DIR / paper_id
    if paper_dir.exists():
        shutil.rmtree(paper_dir)

    paper_sessions.pop(paper_id, None)
    paper_trees.pop(paper_id, None)
    paper_contents.pop(paper_id, None)

    return True
