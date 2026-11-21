"""
[THÀNH VIÊN B] - Quản lý kết nối TCP P2P và các luồng nhận/gửi dữ liệu.
Đảm nhận:
- Thread 4 (TCP Acceptor): Lắng nghe kết nối TCP mới từ các peer khác.
- Thread 5 (TCP Receiver - 1 luồng cho mỗi peer): Đọc khung tin MSG, FILE, BYE từ socket của peer đó.
"""

import socket
import threading
from typing import Dict, Optional
from core.models import PeerInfo
from core.shared_state import SharedState
from network.file_transfer import FileTransferService


class TCPConnectionManager:
    """
    Quản lý vòng đời của TCP Server (Acceptor) và các kết nối TCP P2P tới từng peer.
    """

    def __init__(
        self,
        shared_state: SharedState,
        signals: object,
        listen_port: int,
        download_dir: str = "downloads",
    ) -> None:
        self.shared_state = shared_state
        self.signals = signals
        self.listen_port = listen_port
        self.download_dir = download_dir

        self._running = False
        self._server_sock: Optional[socket.socket] = None
        self._acceptor_thread: Optional[threading.Thread] = None

        # Bảo vệ bảng kết nối các socket đang mở: key là peer_id ("<ip>:<tcp_port>")
        self._conn_lock = threading.Lock()
        self._connections: Dict[str, socket.socket] = {}
        # Khóa gửi dữ liệu cho từng peer để tránh 2 luồng ghi đè byte lên cùng 1 socket
        self._send_locks: Dict[str, threading.Lock] = {}

        # Dịch vụ truyền file (Thread 6)
        self.file_service = FileTransferService(
            shared_state=self.shared_state,
            signals=self.signals,
            download_dir=self.download_dir,
        )

    def start_server(self) -> None:
        """
        Khởi tạo TCP Server socket tại cổng `self.listen_port` và bắt đầu chạy Thread 4 (TCP Acceptor).
        TODO [Thành viên B]:
        1. Tạo socket AF_INET, SOCK_STREAM, bật SO_REUSEADDR, bind(("", self.listen_port)), listen().
        2. Khởi chạy luồng _acceptor_loop (daemon=True).
        """
        pass

    def connect_to_peer(self, peer: PeerInfo) -> bool:
        """
        Mở kết nối TCP chủ động tới `peer` (khi người dùng gõ `/chat <name|number>` hoặc click trên GUI).
        - Nếu đã có kết nối sống trong `self._connections[peer.peer_id]`, tái sử dụng kết nối đó.
        - Nếu chưa có, tạo socket mới `connect((peer.ip, peer.tcp_port))` và khởi chạy Thread 5 (`_receiver_loop`).
        - Nếu peer đã offline hoặc từ chối kết nối, bắt lỗi OSError/ConnectionRefusedError, bắn thông báo lỗi lên UI và trả về False.
        TODO [Thành viên B]: Hiện thực kết nối TCP chủ động tới peer.
        """
        return False

    def send_text_message(self, peer_id: str, text: str) -> bool:
        """
        Đóng gói tin nhắn bằng `protocol.encode_msg(text)` và gửi qua socket của `peer_id`.
        Trả về True nếu gửi thành công, False nếu lỗi kết nối.
        TODO [Thành viên B]: Sử dụng khóa gửi (_send_locks) và sock.sendall() để gửi an toàn.
        """
        return False

    def send_file_async(self, peer_id: str, filepath: str) -> None:
        """
        Gọi `self.file_service.start_send_file_thread(...)` để truyền file trên Thread 6
        mà không làm nghẽn việc gửi/nhận tin nhắn chat.
        TODO [Thành viên B]: Kiểm tra kết nối và ủy quyền cho FileTransferService.
        """
        pass

    def disconnect_peer(self, peer_id: str) -> None:
        """
        Ngắt kết nối với 1 peer cụ thể (khi người dùng gõ `/leave`):
        Gửi khung `BYE|` và đóng socket của peer đó.
        TODO [Thành viên B]: Hiện thực đóng kết nối đơn lẻ an toàn.
        """
        pass

    def stop_all(self) -> None:
        """
        Đóng TCP Acceptor và gửi `BYE|` tới toàn bộ các peer đang kết nối khi thoát ứng dụng (`/quit`).
        TODO [Thành viên B]: Hiện thực dọn dẹp tài nguyên mạng.
        """
        pass

    def _acceptor_loop(self) -> None:
        """
        [Thread 4 - TCP Acceptor]
        Vòng lặp chờ `self._server_sock.accept()`.
        Mỗi khi có kết nối mới đến, khởi tạo một luồng `_receiver_loop` (Thread 5) cho kết nối đó.
        TODO [Thành viên B]: Hiện thực vòng lặp chấp nhận kết nối.
        """
        pass

    def _receiver_loop(self, conn: socket.socket, peer_id: str) -> None:
        """
        [Thread 5 - TCP Receiver (mỗi peer 1 luồng)]
        Vòng lặp đọc khung dữ liệu từ `conn` bằng `protocol.read_frame_header(conn)`:
        1. Nếu là 'MSG': Dùng `recv_exact` đọc đủ `<length>` bytes, giải mã UTF-8,
           lưu vào `self.shared_state.append_message(...)` và bắn tín hiệu lên GUI.
        2. Nếu là 'FILE': Gọi `self.file_service.receive_file_stream(...)` để lưu vào `downloads/`.
        3. Nếu là 'BYE' hoặc mất kết nối (ConnectionError): Đóng socket, xóa khỏi `_connections`
           và bắn tín hiệu `self.signals.peer_disconnected.emit(peer_id, reason)`.
        TODO [Thành viên B]: Hiện thực vòng lặp nhận dữ liệu cho từng peer.
        """
        pass
