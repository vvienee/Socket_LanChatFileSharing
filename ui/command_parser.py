"""
[THÀNH VIÊN C] - Bộ phân tích cú pháp lệnh (Command Parser).
Hỗ trợ đầy đủ các lệnh theo đặc tả trong plan.md:
- /list
- /chat <name|number>
- /send <file>
- /leave
- /status <online|away>
- /help
- /quit
Và văn bản thông thường (gửi tin nhắn chat tới active peer).
"""

from typing import Callable, Optional
from core.shared_state import SharedState
from core.udp_discovery import UDPDiscoveryService
from network.tcp_manager import TCPConnectionManager


class CommandParser:
    """
    Phân tích chuỗi người dùng nhập vào từ ô chat của PySide6 (hoặc từ các nút bấm trên GUI)
    và điều phối xuống các dịch vụ của Thành viên A và Thành viên B.
    """

    def __init__(
        self,
        shared_state: SharedState,
        udp_service: UDPDiscoveryService,
        tcp_manager: TCPConnectionManager,
        signals: object,
        on_quit_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        self.shared_state = shared_state
        self.udp_service = udp_service
        self.tcp_manager = tcp_manager
        self.signals = signals
        self.on_quit_callback = on_quit_callback

    def handle_user_input(self, raw_text: str) -> None:
        """
        Điểm vào chính khi người dùng nhấn Enter tại ô nhập liệu.
        - Nếu bắt đầu bằng '/': Tách lệnh và tham số, gọi hàm xử lý tương ứng (`_cmd_*`).
        - Nếu là văn bản bình thường: Gửi tin nhắn tới peer đang chat hiện tại.
        TODO [Thành viên C]: Hiện thực điều phối lệnh và xử lý lệnh không hợp lệ.
        """
        pass

    def _cmd_list(self) -> None:
        """
        Lệnh `/list`: Hiển thị danh sách người dùng đang online kèm số thứ tự, tên, IP và trạng thái.
        TODO [Thành viên C]: Đọc từ `self.shared_state.get_online_peers()` và hiển thị qua `signals.system_notification`.
        """
        pass

    def _cmd_chat(self, target: str) -> None:
        """
        Lệnh `/chat <name|number>`:
        1. Tìm peer bằng `self.shared_state.find_peer(target)`.
        2. Gọi `self.tcp_manager.connect_to_peer(peer)`.
        3. Nếu kết nối thành công, gọi `self.shared_state.set_active_chat(peer.peer_id)`
           để lấy lịch sử + các tin nhắn chưa đọc và hiển thị lên khung chat.
        TODO [Thành viên C]: Hiện thực logic mở phiên chat.
        """
        pass

    def _cmd_send(self, filepath: str) -> None:
        """
        Lệnh `/send <file>`: Gửi file tới người đang chat hiện tại.
        TODO [Thành viên C]: Kiểm tra đang có active_chat hay không và gọi `self.tcp_manager.send_file_async(...)`.
        """
        pass

    def _cmd_leave(self) -> None:
        """
        Lệnh `/leave`: Đóng cuộc trò chuyện hiện tại và quay về màn hình chờ chính.
        TODO [Thành viên C]: Gọi `self.tcp_manager.disconnect_peer(...)` và `self.shared_state.set_active_chat(None)`.
        """
        pass

    def _cmd_status(self, new_status: str) -> None:
        """
        Lệnh `/status <online|away>`: Đổi trạng thái hiện diện của bản thân và phát UDP broadcast ngay lập tức.
        TODO [Thành viên C]: Kiểm tra giá trị 'online'/'away', cập nhật SharedState và gọi `udp_service.send_immediate_broadcast()`.
        """
        pass

    def _cmd_help(self) -> None:
        """
        Lệnh `/help`: Hiển thị danh sách toàn bộ các lệnh được hỗ trợ.
        TODO [Thành viên C]: Phát thông báo hướng dẫn các lệnh lên khung chat.
        """
        pass

    def _cmd_quit(self) -> None:
        """
        Lệnh `/quit`: Đóng các kết nối mạng và thoát chương trình an toàn.
        TODO [Thành viên C]: Gọi `udp_service.stop()`, `tcp_manager.stop_all()`, và `on_quit_callback()`.
        """
        pass
