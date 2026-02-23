from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional, List, Dict
from backend.models import Message, ConversationBranch, PaperSession


class ConversationTree:
    def __init__(self):
        self.branches: Dict[str, ConversationBranch] = {}
        self.root_branch_id: Optional[str] = None

    def create_branch(
        self, name: str, parent_message_id: Optional[str] = None
    ) -> ConversationBranch:
        branch_id = str(uuid.uuid4())[:8]
        branch = ConversationBranch(
            id=branch_id, name=name, messages=[], created_at=datetime.now().isoformat()
        )
        self.branches[branch_id] = branch
        if not self.root_branch_id:
            self.root_branch_id = branch_id
        return branch

    def add_message_to_branch(self, branch_id: str, message: Message):
        if branch_id in self.branches:
            self.branches[branch_id].messages.append(message)

    def get_branch(self, branch_id: str) -> Optional[ConversationBranch]:
        return self.branches.get(branch_id)

    def get_all_branches(self) -> List[ConversationBranch]:
        return list(self.branches.values())

    def get_branch_context(
        self, branch_id: str, up_to_message_id: Optional[str] = None
    ) -> List[Message]:
        branch = self.get_branch(branch_id)
        if not branch:
            return []

        if up_to_message_id:
            messages = []
            for msg in branch.messages:
                messages.append(msg)
                if msg.id == up_to_message_id:
                    break
            return messages
        return branch.messages

    def create_child_branch(
        self, parent_branch_id: str, parent_message_id: str, name: Optional[str] = None
    ) -> ConversationBranch:
        parent_branch = self.get_branch(parent_branch_id)
        if not parent_branch:
            raise ValueError(f"Parent branch {parent_branch_id} not found")

        branch_name = name or f"分支 {len(self.branches) + 1}"
        new_branch = self.create_branch(branch_name)

        new_branch.with_context = getattr(parent_branch, "with_context", True)

        context_messages = self.get_branch_context(parent_branch_id, parent_message_id)
        for msg in context_messages:
            new_msg = Message(
                id=str(uuid.uuid4())[:8],
                role=msg.role,
                content=msg.content,
                timestamp=datetime.now().isoformat(),
                is_initial=msg.is_initial,
                prompt_name=msg.prompt_name,
            )
            new_branch.messages.append(new_msg)

        return new_branch

    def to_dict(self) -> Dict:
        return {
            "branches": {
                bid: branch.model_dump() for bid, branch in self.branches.items()
            },
            "root_branch_id": self.root_branch_id,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ConversationTree":
        tree = cls()
        for bid, bdata in data.get("branches", {}).items():
            tree.branches[bid] = ConversationBranch(**bdata)
        tree.root_branch_id = data.get("root_branch_id")
        return tree


class PaperSessionManager:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.sessions: Dict[str, PaperSession] = {}

    def create_session(
        self, paper_id: str, filename: str, text_content: str
    ) -> PaperSession:
        session = PaperSession(
            id=paper_id,
            filename=filename,
            text_content=text_content,
            branches=[],
            created_at=datetime.now().isoformat(),
        )
        self.sessions[paper_id] = session
        return session

    def get_session(self, paper_id: str) -> Optional[PaperSession]:
        return self.sessions.get(paper_id)

    def add_branch_to_session(self, paper_id: str, branch: ConversationBranch):
        session = self.get_session(paper_id)
        if session:
            session.branches.append(branch)

    def to_dict(self) -> Dict:
        return {pid: session.model_dump() for pid, session in self.sessions.items()}
