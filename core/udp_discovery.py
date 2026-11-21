"""
[THÀNH VIÊN A] - Dịch vụ khám phá người dùng trong mạng LAN bằng UDP Broadcast.
Quản lý 2 luồng theo đặc tả kỹ thuật:
- Thread 2 (UDP Broadcaster): Phát bản tin HELLO|<name>|<tcp_port>|<status> mỗi 3 giây.
- Thread 3 (UDP Listener): Lắng nghe cổng UDP 9999, cập nhật danh sách peer và quét timeout 10 giây.
"""

import socket
import threading
from typing import Optional
from core.shared_state import SharedState


class UDPDiscoveryService:
    """
    Quản lý việc phát và nhận tín hiệu hiện diện (Presence) qua giao thức UDP.
    """

    DEFAULT_UDP_PORT = 9999
    BROADCAST_INTERVAL_SEC = 3.0
    PEER_TIMEOUT_SEC = 10.0

    def __init__(
        self,
        shared_state: SharedState,
        signals: object,
        udp_port: int = DEFAULT_UDP_PORT,
        broadcast_ip: str = "255.255.255.255",
    ) -> None:
        """
        Khởi tạo dịch vụ UDP Discovery.
        :param shared_state: Đối tượng SharedState dùng chung.
        :param signals: Đối tượng AppSignals (ui/qt_signals.py) để bắn sự kiện lên GUI.
        :param udp_port: Cổng UDP cố định (mặc định 9999).
        :param broadcast_ip: Địa chỉ broadcast ('255.255.255.255' cho LAN hoặc '127.255.255.255' khi test 1 máy).
        """
        self.shared_state = shared_state
        self.signals = signals
        self.udp_port = udp_port
        self.broadcast_ip = broadcast_ip

        self._running = False
        self._broadcaster_thread: Optional[threading.Thread] = None
        self._listener_thread: Optional[threading.Thread] = None
        self._send_sock: Optional[socket.socket] = None
        self._recv_sock: Optional[socket.socket] = None

    def start(self) -> None:
        """
        Khởi tạo UDP sockets và bắt đầu chạy 2 luồng daemon:
        - _broadcaster_loop (Thread 2)
        - _listener_loop (Thread 3)
        TODO [Thành viên A]:
        1. Cấu hình _recv_sock với SO_REUSEADDR và SO_BROADCAST, bind(("", self.udp_port)).
        2. Đặt settimeout(1.0) cho _recv_sock để vòng lặp có thể kiểm tra self._running và quét timeout 10s định kỳ.
        3. Khởi chạy 2 luồng với daemon=True.
        """
        pass

    def stop(self) -> None:
        """
        Dừng 2 luồng UDP và đóng các socket an toàn khi thoát chương trình (/quit).
        TODO [Thành viên A]: Đặt self._running = False và đóng _send_sock, _recv_sock.
        """
        pass

    def send_immediate_broadcast(self) -> None:
        """
        Gửi ngay lập tức 1 gói tin UDP HELLO (dùng khi người dùng vừa đổi /status <online|away>
        để các peer khác thấy ngay mà không cần đợi hết chu kỳ 3 giây).
        TODO [Thành viên A]: Đóng gói 'HELLO|<name>|<tcp_port>|<status>' và sendto((self.broadcast_ip, self.udp_port)).
        """
        pass

    def _broadcaster_loop(self) -> None:
        """
        [Thread 2 - UDP Broadcaster]
        Vòng lặp định kỳ mỗi 3 giây đọc thông tin từ self.shared_state.get_my_info()
        và gửi gói tin UDP broadcast.
        TODO [Thành viên A]: Hiện thực vòng lặp phát broadcast mỗi 3s.
        """
        pass

    def _listener_loop(self) -> None:
        """
        [Thread 3 - UDP Listener]
        Vòng lặp nhận datagram từ cổng 9999:
        1. Bóc tách gói tin 'HELLO|<name>|<tcp_port>|<status>'.
        2. Gọi self.shared_state.upsert_peer(...).
        3. Nếu có peer mới vào ('joined') hoặc đổi trạng thái ('status_changed'),
           bắn tín hiệu self.signals.peer_list_updated.emit() và self.signals.system_notification.emit(...).
        4. Định kỳ gọi self.shared_state.remove_expired_peers(10.0) để xóa peer mất kết nối quá 10s
           và thông báo lên UI khi có peer offline.
        TODO [Thành viên A]: Hiện thực vòng lặp lắng nghe và kiểm tra timeout 10s.
        """
        pass
