"""Kho dữ liệu dùng chung giữa các luồng (Thành viên A).

Mọi phương thức public đều lấy threading.RLock và trả về BẢN SAO của PeerInfo,
nên caller (thread khác) có thể đọc thoải mái mà không cần giữ lock.
"""
import dataclasses
import threading
import time
from typing import Dict, List, Optional, Tuple

from .models import ChatMessage, PeerInfo, ONLINE, VALID_STATUSES


class SharedState:
    def __init__(self, my_name: str, my_tcp_port: int):
        if not my_name or "|" in my_name:
            raise ValueError("name must be non-empty and must not contain '|'")
        self._lock = threading.RLock()
        self._my_name = my_name
        self._my_port = my_tcp_port
        self._my_status = ONLINE
        self._peers: Dict[str, PeerInfo] = {}              # peer_id -> PeerInfo
        self._histories: Dict[str, List[ChatMessage]] = {}  # peer_id -> messages
        self._unread: Dict[str, int] = {}                   # peer_id -> unread
        self._active_id: Optional[str] = None

    # ------------------------------------------------------- bản thân
    def set_my_status(self, status: str) -> None:
        if status not in VALID_STATUSES:
            raise ValueError("status must be 'online' or 'away'")
        with self._lock:
            self._my_status = status

    def get_my_info(self) -> Tuple[str, int, str]:
        with self._lock:
            return self._my_name, self._my_port, self._my_status

    # ------------------------------------------------------- danh sách peer
    def upsert_peer(self, name: str, ip: str, tcp_port: int, status: str) -> Optional[str]:
        """Thêm/cập nhật peer. Trả về "joined" (mới), "status_changed", hoặc None (chỉ làm mới last_seen)."""
        with self._lock:
            peer_id = f"{ip}:{tcp_port}"
            old = self._peers.get(peer_id)
            # Cùng tên nhưng khác ip:port (peer khởi động lại với cổng khác) -> bỏ bản cũ.
            for pid in [p.peer_id for p in self._peers.values()
                        if p.name == name and p.peer_id != peer_id]:
                del self._peers[pid]
            self._peers[peer_id] = PeerInfo(name, ip, tcp_port, status, time.time())
            if old is None:
                return "joined"
            return "status_changed" if old.status != status else None

    def remove_expired_peers(self, timeout_sec: float = 10.0) -> List[PeerInfo]:
        now = time.time()
        with self._lock:
            gone = [p for p in self._peers.values() if now - p.last_seen > timeout_sec]
            for p in gone:
                del self._peers[p.peer_id]
            return [dataclasses.replace(p) for p in gone]

    def get_online_peers(self) -> List[PeerInfo]:
        """Sắp xếp theo tên -> số thứ tự ổn định cho /list và /chat <số>."""
        with self._lock:
            return [dataclasses.replace(p) for p in
                    sorted(self._peers.values(), key=lambda p: (p.name.lower(), p.peer_id))]

    def get_peer(self, peer_id: str) -> Optional[PeerInfo]:
        with self._lock:
            p = self._peers.get(peer_id)
            return dataclasses.replace(p) if p else None

    def find_peer(self, target: str) -> Optional[PeerInfo]:
        """target: số thứ tự (từ 1, như /list), tên (không phân biệt hoa/thường) hoặc peer_id."""
        target = target.strip()
        peers = self.get_online_peers()
        if target.isdigit():
            i = int(target)
            return peers[i - 1] if 1 <= i <= len(peers) else None
        for p in peers:
            if p.name.lower() == target.lower() or p.peer_id == target:
                return p
        return None

    # ------------------------------------- chat đang mở / lịch sử / unread
    def set_active_chat(self, peer_id: Optional[str]) -> List[ChatMessage]:
        """Đặt đối tác chat hiện tại, reset unread của họ, trả về toàn bộ lịch sử tin nhắn."""
        with self._lock:
            self._active_id = peer_id
            if peer_id is None:
                return []
            self._unread[peer_id] = 0
            return list(self._histories.get(peer_id, []))

    def get_active_chat(self) -> Optional[PeerInfo]:
        """Peer đang chat; None nếu chưa chọn hoặc peer đã offline."""
        with self._lock:
            return self.get_peer(self._active_id) if self._active_id else None

    def get_active_chat_id(self) -> Optional[str]:
        with self._lock:
            return self._active_id

    def append_message(self, peer_id: str, msg: ChatMessage) -> int:
        """Lưu tin nhắn. Nếu peer_id KHÔNG phải chat hiện tại thì tăng unread.
        Trả về số unread hiện tại của peer_id (0 nếu đang chat với họ)."""
        with self._lock:
            self._histories.setdefault(peer_id, []).append(msg)
            if peer_id != self._active_id and not msg.is_system and msg.sender_id == peer_id:
                self._unread[peer_id] = self._unread.get(peer_id, 0) + 1
            return self._unread.get(peer_id, 0)

    def get_unread_count(self, peer_id: str) -> int:
        with self._lock:
            return self._unread.get(peer_id, 0)
