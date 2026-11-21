"""
[THÀNH VIÊN A] - Quản lý dữ liệu dùng chung (SharedState) giữa 6 luồng.
Tất cả thao tác đọc/ghi trên danh sách peers, lịch sử chat, unread count
PHẢI được bảo vệ bằng self._lock (threading.RLock).
"""

import threading
from typing import Dict, List, Optional, Tuple
from core.models import PeerInfo, ChatMessage


class SharedState:
    """
    Lớp lưu trữ trạng thái toàn cục của ứng dụng.
    An toàn đa luồng (Thread-safe) nhờ sử dụng threading.RLock.
    """

    def __init__(self, my_name: str, my_tcp_port: int, initial_status: str = "online") -> None:
        self._lock = threading.RLock()
        self.my_name: str = my_name
        self.my_tcp_port: int = my_tcp_port
        self.my_status: str = initial_status  # "online" | "away"

        # Danh sách các peer đang online: key là peer_id ("<ip>:<tcp_port>")
        self.peers: Dict[str, PeerInfo] = {}

        # Lịch sử tin nhắn theo từng peer_id
        self.chat_histories: Dict[str, List[ChatMessage]] = {}

        # Bộ đếm số tin nhắn chưa đọc theo từng peer_id
        self.unread_counts: Dict[str, int] = {}

        # peer_id của người đang được chọn để chat hiện tại (None nếu chưa chọn ai)
        self.active_chat_peer_id: Optional[str] = None

    def set_my_status(self, status: str) -> None:
        """
        Cập nhật trạng thái của bản thân ('online' hoặc 'away').
        TODO [Thành viên A]: Dùng self._lock để kiểm tra hợp lệ và cập nhật self.my_status.
        """
        pass

    def get_my_info(self) -> Tuple[str, int, str]:
        """
        Trả về bộ 3 (my_name, my_tcp_port, my_status).
        TODO [Thành viên A]: Bảo vệ bằng self._lock và trả về tuple thông tin cá nhân.
        """
        return (self.my_name, self.my_tcp_port, self.my_status)

    def upsert_peer(self, name: str, ip: str, tcp_port: int, status: str) -> Optional[str]:
        """
        Thêm mới hoặc cập nhật thông tin một peer khi nhận được bản tin UDP HELLO.
        - Bỏ qua nếu là gói tin của chính mình (trùng tcp_port và IP local).
        - Cập nhật last_seen = time.time().
        - Trả về:
            + "joined": Nếu peer mới xuất hiện lần đầu.
            + "status_changed": Nếu peer đã có mặt nhưng đổi status (online <-> away) hoặc đổi tên.
            + None: Nếu chỉ cập nhật last_seen bình thường.
        TODO [Thành viên A]: Hiện thực logic trên bên trong self._lock.
        """
        pass

    def remove_expired_peers(self, timeout_sec: float = 10.0) -> List[PeerInfo]:
        """
        Quét và xóa các peer không gửi gói tin UDP nào trong khoảng thời gian timeout_sec (mặc định 10s).
        Trả về danh sách các PeerInfo vừa bị xóa để thông báo lên UI.
        TODO [Thành viên A]: Hiện thực logic lọc và xóa peer quá hạn bên trong self._lock.
        """
        return []

    def get_online_peers(self) -> List[PeerInfo]:
        """
        Trả về bản sao (copy) danh sách các PeerInfo đang online để hiển thị cho lệnh /list hoặc Sidebar.
        TODO [Thành viên A]: Dùng self._lock và trả về list(self.peers.values()).
        """
        return []

    def find_peer(self, target: str) -> Optional[PeerInfo]:
        """
        Tìm kiếm peer dựa vào:
        1. Số thứ tự (1-based index theo danh sách get_online_peers(), ví dụ "1", "2").
        2. Tên người dùng (không phân biệt hoa thường, ví dụ "Minh").
        3. Định danh peer_id ("192.168.1.12:5000").
        TODO [Thành viên A]: Hiện thực logic tìm kiếm phục vụ lệnh /chat <name|number>.
        """
        return None

    def set_active_chat(self, peer_id: Optional[str]) -> List[ChatMessage]:
        """
        Đặt peer đang chat hiện tại (hoặc None khi /leave).
        Nếu peer_id khác None, tự động reset unread_counts[peer_id] = 0
        và trả về toàn bộ lịch sử ChatMessage của peer đó.
        TODO [Thành viên A]: Hiện thực logic chuyển cuộc trò chuyện bên trong self._lock.
        """
        return []

    def get_active_chat(self) -> Optional[PeerInfo]:
        """
        Trả về đối tượng PeerInfo của người đang chat hiện tại (hoặc None nếu không trong phòng chat nào).
        TODO [Thành viên A]: Hiện thực bên trong self._lock.
        """
        return None

    def append_message(self, peer_id: str, msg: ChatMessage) -> int:
        """
        Thêm một tin nhắn mới vào lịch sử chat với peer_id.
        - Nếu peer_id != self.active_chat_peer_id (và không phải tin nhắn do chính mình gửi):
          Tăng self.unread_counts[peer_id] lên 1.
        - Trả về giá trị unread_counts[peer_id] sau khi cập nhật.
        TODO [Thành viên A]: Hiện thực logic lưu lịch sử và tăng bộ đếm unread.
        """
        return 0

    def get_unread_count(self, peer_id: str) -> int:
        """
        Lấy số lượng tin nhắn chưa đọc của một peer_id.
        TODO [Thành viên A]: Hiện thực bên trong self._lock.
        """
        return 0
