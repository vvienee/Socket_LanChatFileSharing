"""Khám phá người dùng bằng UDP Broadcast (Thành viên A).

  Thread 2 (broadcaster): gửi  HELLO|<name>|<tcp_port>|<status>  mỗi 3 giây
                          (hoặc ngay lập tức khi gọi send_immediate_broadcast()).
  Thread 3 (listener)   : nhận gói trên cổng UDP, upsert vào SharedState, mỗi 1 giây
                          quét xóa peer im lặng > 10 giây.

`signals` (tùy chọn) là đối tượng duck-typed có
    signals.peer_list_updated.emit()
    signals.system_notification.emit(str)
nên truyền thẳng AppSignals của C vào; core không import Qt.
Định dạng gói HELLO tự phân tích tại đây (giống network/protocol.py) để A chạy độc lập với B.
"""
import socket
import threading
import time

from .models import VALID_STATUSES
from .shared_state import SharedState


class UDPDiscoveryService:
    def __init__(self, state: SharedState, udp_port: int = 9999,
                 broadcast_addr: str = "255.255.255.255", signals=None,
                 interval: float = 3.0, timeout: float = 10.0, scan_interval: float = 1.0):
        self.state = state
        self.udp_port = udp_port
        self.broadcast_addr = broadcast_addr
        self.signals = signals
        self.interval = interval
        self.timeout = timeout
        self.scan_interval = scan_interval
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._threads = []
        self._rx = None

    # ---------------------------------------------------------- điều khiển
    def start(self) -> None:
        """Bind socket ngay trong lời gọi (cổng bận -> OSError báo sớm), rồi chạy 2 thread."""
        rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):          # không có trên Windows
            rx.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        rx.bind(("", self.udp_port))
        rx.settimeout(min(self.scan_interval, 0.5))
        self._rx = rx
        self._stop.clear()
        for target, name in ((self._broadcast_loop, "udp-broadcaster"),
                             (self._listen_loop, "udp-listener")):
            t = threading.Thread(target=target, name=name, daemon=True)
            t.start()
            self._threads.append(t)

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        for t in self._threads:
            t.join(timeout=2)
        self._threads.clear()
        if self._rx:
            self._rx.close()
            self._rx = None

    def send_immediate_broadcast(self) -> None:
        """Gọi sau state.set_my_status() để phát HELLO ngay, không chờ chu kỳ 3s."""
        self._wake.set()

    # ------------------------------------------------------------ Thread 2
    def _broadcast_loop(self) -> None:
        tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        tx.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            while not self._stop.is_set():
                name, port, status = self.state.get_my_info()
                try:
                    tx.sendto(f"HELLO|{name}|{port}|{status}".encode("utf-8"),
                              (self.broadcast_addr, self.udp_port))
                except OSError:
                    pass                  # UDP: mất gói chấp nhận được
                self._wake.wait(self.interval)
                self._wake.clear()
        finally:
            tx.close()

    # ------------------------------------------------------------ Thread 3
    def _listen_loop(self) -> None:
        last_scan = time.time()
        while not self._stop.is_set():
            try:
                data, (ip, _) = self._rx.recvfrom(1024)
                self._handle_packet(data, ip)
            except socket.timeout:
                pass
            except OSError:
                break
            if time.time() - last_scan >= self.scan_interval:
                last_scan = time.time()
                self._scan_timeouts()

    def _handle_packet(self, data: bytes, ip: str) -> None:
        try:
            kind, name, port, status = data.decode("utf-8").split("|")
            port = int(port)
        except (UnicodeDecodeError, ValueError):
            return                        # gói rác -> bỏ qua
        my_name = self.state.get_my_info()[0]
        if kind != "HELLO" or not name or name == my_name:
            return                        # lọc gói của chính mình
        if status not in VALID_STATUSES or not 0 < port < 65536:
            return
        result = self.state.upsert_peer(name, ip, port, status)
        if result == "joined":
            self._emit_notification(f"[*] {name} is now online")
        if result is not None:
            self._emit_list_updated()

    def _scan_timeouts(self) -> None:
        gone = self.state.remove_expired_peers(self.timeout)
        for p in gone:
            self._emit_notification(f"[*] {p.name} went offline")
        if gone:
            self._emit_list_updated()

    # ------------------------------------------------------------ signals
    def _emit_list_updated(self):
        self._safe(lambda: self.signals.peer_list_updated.emit())

    def _emit_notification(self, text):
        self._safe(lambda: self.signals.system_notification.emit(text))

    def _safe(self, fn):
        if self.signals is None:
            return
        try:
            fn()
        except Exception as e:            # lỗi UI không được giết thread mạng
            print(f"[!] signal error: {e}")
