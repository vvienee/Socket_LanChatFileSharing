"""Data Contract dùng chung cho cả nhóm (Thành viên A)."""
import time
import uuid
from dataclasses import dataclass, field

ONLINE = "online"
AWAY = "away"
VALID_STATUSES = (ONLINE, AWAY)
RECALL_PREFIX = "__LANCHAT_RECALL__|"
REACT_PREFIX = "__LANCHAT_REACT__|"
REPLY_PREFIX = "__LANCHAT_REPLY__|"


@dataclass
class PeerInfo:
    name: str
    ip: str
    tcp_port: int
    status: str = ONLINE
    last_seen: float = field(default_factory=time.time)

    @property
    def peer_id(self) -> str:
        """Định danh duy nhất của peer: '<ip>:<tcp_port>' (cổng LẮNG NGHE TCP của peer)."""
        return f"{self.ip}:{self.tcp_port}"


@dataclass
class ChatMessage:
    sender_name: str
    sender_id: str
    content: str
    timestamp: float = field(default_factory=time.time)
    is_system: bool = False
    msg_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    is_recalled: bool = False
    is_file: bool = False
    file_name: str = ""
    file_size: int = 0
    file_path: str = ""
    reactions: dict = field(default_factory=dict)
    reply_to_text: str = ""


@dataclass
class FileTransferProgress:
    peer_id: str
    filename: str
    transferred_bytes: int
    total_bytes: int
    direction: str          # "send" | "receive"

    @property
    def percent(self) -> int:
        if self.total_bytes <= 0:
            return 100
        return min(100, self.transferred_bytes * 100 // self.total_bytes)
