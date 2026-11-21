"""
[THÀNH VIÊN A] - Định nghĩa các Data Models (Hợp đồng dữ liệu chung cho A, B, C).
Các thành viên B và C import trực tiếp các lớp này để sử dụng.
"""

from dataclasses import dataclass, field
import time


@dataclass
class PeerInfo:
    """Thông tin của một người dùng (peer) trong mạng LAN."""
    name: str
    ip: str
    tcp_port: int
    status: str = "online"  # Giá trị hợp lệ: "online" | "away"
    last_seen: float = field(default_factory=time.time)

    @property
    def peer_id(self) -> str:
        """
        Định danh duy nhất cho mỗi peer theo định dạng '<ip>:<tcp_port>'.
        Giúp phân biệt nhiều tiến trình chạy trên cùng 1 máy (cùng IP nhưng khác TCP port).
        """
        return f"{self.ip}:{self.tcp_port}"


@dataclass
class ChatMessage:
    """Cấu trúc một tin nhắn lưu trong lịch sử chat."""
    sender_name: str
    sender_id: str          # peer_id ('<ip>:<tcp_port>') hoặc 'SELF' / 'SYSTEM'
    content: str
    timestamp: float = field(default_factory=time.time)
    is_system: bool = False


@dataclass
class FileTransferProgress:
    """Thông tin tiến độ truyền file để hiển thị lên GUI."""
    peer_id: str
    filename: str
    transferred_bytes: int
    total_bytes: int
    direction: str = "send"  # "send" | "receive"

    @property
    def percentage(self) -> int:
        """Tính phần trăm hoàn thành (0 - 100)."""
        if self.total_bytes <= 0:
            return 0
        return min(100, int((self.transferred_bytes * 100) / self.total_bytes))
