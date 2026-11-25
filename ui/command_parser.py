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

Quy ước hiển thị (giống ví dụ trong plan.md):
- "[*] ..." : thông báo thông tin.
- "[!] ..." : thông báo lỗi / cảnh báo.

Mọi phương thức của lớp này được gọi từ Main Thread (Thread 1) - khi người dùng nhấn Enter,
bấm nút hoặc click trên Sidebar. Kết quả được đẩy lên GUI qua `AppSignals`, CommandParser
không bao giờ chạm trực tiếp vào widget.
"""

import os
import sys
import traceback
from typing import Callable, Dict, Optional

from core.models import ChatMessage, PeerInfo
from core.shared_state import SharedState
from core.udp_discovery import UDPDiscoveryService
from network.tcp_manager import TCPConnectionManager

VALID_STATUSES = ("online", "away")
SELF_SENDER_ID = "SELF"

HELP_TEXT = (
    "[*] Available commands:\n"
    "    /list                   Show online users (number, name, IP, status)\n"
    "    /chat <name|number>     Open a chat with the selected user (TCP)\n"
    "    <any text>              Send a message to the current chat partner\n"
    "    /send <file>            Send a file to the current chat partner\n"
    "    /leave                  Close the current chat\n"
    "    /status <online|away>   Change your status (sent via UDP)\n"
    "    /help                   Show all commands\n"
    "    /quit                   Exit the program\n"
    "    Tip: click a user in the sidebar to chat, use 'Send File...' to pick a file."
)


def format_size(num_bytes: int) -> str:
    """Định dạng kích thước file dễ đọc: 512 B, 3.4 KB, 2.4 MB, 1.1 GB."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


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
        self._is_shut_down = False

        # Bảng điều phối: tên lệnh -> hàm xử lý nhận 1 tham số chuỗi (có thể rỗng)
        self._commands: Dict[str, Callable[[str], None]] = {
            "/list": lambda _arg: self._cmd_list(),
            "/chat": self._cmd_chat,
            "/send": self._cmd_send,
            "/leave": lambda _arg: self._cmd_leave(),
            "/status": self._cmd_status,
            "/help": lambda _arg: self._cmd_help(),
            "/quit": lambda _arg: self._cmd_quit(),
        }

    # ------------------------------------------------------------------
    # Điểm vào chính
    # ------------------------------------------------------------------

    def handle_user_input(self, raw_text: str) -> None:
        """
        Điểm vào chính khi người dùng nhấn Enter tại ô nhập liệu.
        - Nếu bắt đầu bằng '/': Tách lệnh và tham số, gọi hàm xử lý tương ứng (`_cmd_*`).
        - Nếu là văn bản bình thường: Gửi tin nhắn tới peer đang chat hiện tại.
        Mọi ngoại lệ phát sinh từ tầng dưới đều bị bắt lại để GUI không bao giờ bị crash.
        """
        if raw_text is None:
            return
        text = raw_text.strip()
        if not text:
            return

        if not text.startswith("/"):
            self._guarded("send message", self._send_chat_text, text)
            return

        parts = text.split(maxsplit=1)
        command = parts[0].lower()
        argument = parts[1].strip() if len(parts) > 1 else ""

        handler = self._commands.get(command)
        if handler is None:
            self._notify(f"[!] Unknown command: {command}")
            self._notify("[*] Commands: /list, /chat, /send, /leave, /status, /help, /quit (type /help for details)")
            return

        self._guarded(command, handler, argument)

    # ------------------------------------------------------------------
    # Các lệnh
    # ------------------------------------------------------------------

    def _cmd_list(self) -> None:
        """
        Lệnh `/list`: Hiển thị danh sách người dùng đang online kèm số thứ tự, tên, IP và trạng thái.
        Số thứ tự trùng với thứ tự của `get_online_peers()` nên có thể dùng ngay cho `/chat <number>`.
        """
        peers = self.shared_state.get_online_peers()
        if not peers:
            self._notify("[*] No other users online yet (discovery runs every 3 seconds).")
            return

        active = self.shared_state.get_active_chat()
        active_id = active.peer_id if active else None
        name_width = max(len(p.name) for p in peers)

        lines = [f"[*] Online users ({len(peers)}):"]
        for index, peer in enumerate(peers, start=1):
            unread = self.shared_state.get_unread_count(peer.peer_id)
            extras = []
            if peer.peer_id == active_id:
                extras.append("<- chatting")
            if unread:
                extras.append(f"{unread} unread")
            suffix = f"  [{', '.join(extras)}]" if extras else ""
            lines.append(
                f"  {index}. {peer.name.ljust(name_width)}  ({peer.ip}:{peer.tcp_port})  {peer.status}{suffix}"
            )
        self._notify("\n".join(lines))

    def _cmd_chat(self, target: str) -> None:
        """
        Lệnh `/chat <name|number>`:
        1. Tìm peer bằng `self.shared_state.find_peer(target)`.
        2. Gọi `self.tcp_manager.connect_to_peer(peer)`.
        3. Nếu kết nối thành công, gọi `self.shared_state.set_active_chat(peer.peer_id)`
           để lấy lịch sử + các tin nhắn chưa đọc và hiển thị lên khung chat.
        Lưu ý: chuyển sang chat với người khác KHÔNG đóng kết nối cũ - tin nhắn từ người cũ
        vẫn được nhận và tính vào bộ đếm unread (yêu cầu 3.3 của plan.md).
        """
        target = self._strip_quotes(target)
        if not target:
            self._notify("[!] Usage: /chat <name|number>   (type /list to see numbers)")
            return

        peer = self.shared_state.find_peer(target)
        if peer is None:
            self._notify(f"[!] User '{target}' not found or offline. Type /list to see online users.")
            return

        active = self.shared_state.get_active_chat()
        if active is not None and active.peer_id == peer.peer_id:
            self._notify(f"[*] You are already chatting with {peer.name}.")
            return

        if not self.tcp_manager.connect_to_peer(peer):
            self._notify(f"[!] Could not connect to {peer.name} ({peer.ip}:{peer.tcp_port}). The user may have gone offline.")
            return

        unread = self.shared_state.get_unread_count(peer.peer_id)
        history = self.shared_state.set_active_chat(peer.peer_id)
        self.signals.active_chat_changed.emit(peer, list(history), unread)
        self.signals.peer_list_updated.emit()

        if active is None:
            self._notify(f"[*] Connected to {peer.name} ({peer.ip}:{peer.tcp_port})")
        else:
            self._notify(f"[*] Switched from {active.name} to {peer.name} ({peer.ip}:{peer.tcp_port})")
        if unread:
            self._notify(f"[*] {unread} unread message(s) from {peer.name} shown above.")

    def _cmd_send(self, filepath: str) -> None:
        """
        Lệnh `/send <file>`: Gửi file tới người đang chat hiện tại.
        Hỗ trợ đường dẫn có dấu cách nếu đặt trong ngoặc kép: /send "C:/My Files/slides.pdf".
        """
        filepath = self._strip_quotes(filepath)
        if not filepath:
            self._notify("[!] Usage: /send <file>   (or click 'Send File...')")
            return

        peer = self._require_active_chat()
        if peer is None:
            return

        path = os.path.abspath(os.path.expanduser(filepath))
        if not os.path.isfile(path):
            self._notify(f"[!] File not found: {filepath}")
            return

        try:
            size = os.path.getsize(path)
        except OSError as exc:
            self._notify(f"[!] Cannot read file {filepath}: {exc}")
            return

        self._notify(f"[*] Sending {os.path.basename(path)} ({format_size(size)}) to {peer.name} ...")
        self.tcp_manager.send_file_async(peer.peer_id, path)

    def _cmd_leave(self) -> None:
        """
        Lệnh `/leave`: Đóng cuộc trò chuyện hiện tại và quay về màn hình chờ chính.
        """
        peer = self.shared_state.get_active_chat()
        if peer is None:
            self._notify("[!] You are not in a chat. Use /chat <name|number> first.")
            return

        self.tcp_manager.disconnect_peer(peer.peer_id)
        self.shared_state.set_active_chat(None)
        self.signals.active_chat_changed.emit(None, [], 0)
        self.signals.peer_list_updated.emit()
        self._notify(f"[*] Left the chat with {peer.name}.")

    def _cmd_status(self, new_status: str) -> None:
        """
        Lệnh `/status <online|away>`: Đổi trạng thái hiện diện của bản thân và phát UDP broadcast ngay lập tức.
        """
        status = self._strip_quotes(new_status).lower()
        if status not in VALID_STATUSES:
            self._notify("[!] Usage: /status <online|away>")
            return

        _, _, current = self.shared_state.get_my_info()
        if status == current:
            self._notify(f"[*] Your status is already '{status}'.")
            self.signals.my_status_changed.emit(status)
            return

        self.shared_state.set_my_status(status)
        self.udp_service.send_immediate_broadcast()
        self.signals.my_status_changed.emit(status)
        self._notify(f"[*] Your status is now '{status}' (broadcast via UDP).")

    def _cmd_help(self) -> None:
        """
        Lệnh `/help`: Hiển thị danh sách toàn bộ các lệnh được hỗ trợ.
        """
        self._notify(HELP_TEXT)

    def _cmd_quit(self) -> None:
        """
        Lệnh `/quit`: Đóng các kết nối mạng và thoát chương trình an toàn.
        """
        self._notify("[*] Closing all connections. Bye!")
        self.shutdown()
        if self.on_quit_callback is not None:
            self.on_quit_callback()

    # ------------------------------------------------------------------
    # Tin nhắn thường & dọn dẹp
    # ------------------------------------------------------------------

    def _send_chat_text(self, text: str) -> None:
        """
        Gửi văn bản thường tới active peer. Sau khi tầng TCP (B) gửi thành công,
        lưu tin nhắn của chính mình vào lịch sử (sender_id = 'SELF') và phát lên GUI.
        """
        peer = self._require_active_chat()
        if peer is None:
            return

        if not self.tcp_manager.send_text_message(peer.peer_id, text):
            self._notify(f"[!] Message not delivered: connection to {peer.name} failed. Try /chat {peer.name} again.")
            return

        my_name, _, _ = self.shared_state.get_my_info()
        message = ChatMessage(sender_name=my_name, sender_id=SELF_SENDER_ID, content=text)
        self.shared_state.append_message(peer.peer_id, message)
        self.signals.chat_message_received.emit(peer.peer_id, message)

    def shutdown(self) -> None:
        """
        Dừng toàn bộ dịch vụ mạng đúng 1 lần (idempotent).
        Được gọi từ /quit, từ nút X của cửa sổ (closeEvent) và từ main.py sau khi app.exec() kết thúc.
        """
        if self._is_shut_down:
            return
        self._is_shut_down = True
        for name, action in (("UDP discovery", self.udp_service.stop), ("TCP manager", self.tcp_manager.stop_all)):
            try:
                action()
            except Exception:  # noqa: BLE001 - không được để lỗi dọn dẹp chặn việc thoát
                print(f"[!] Error while stopping {name}:", file=sys.stderr)
                traceback.print_exc()

    @property
    def is_shut_down(self) -> bool:
        return self._is_shut_down

    # ------------------------------------------------------------------
    # Tiện ích nội bộ
    # ------------------------------------------------------------------

    def _require_active_chat(self) -> Optional[PeerInfo]:
        peer = self.shared_state.get_active_chat()
        if peer is None:
            self._notify("[!] No active chat. Select a user with /chat <name|number> (or click a user) first.")
        return peer

    def _notify(self, text: str) -> None:
        self.signals.system_notification.emit(text)

    def _guarded(self, label: str, func: Callable, *args) -> None:
        """Chạy một lệnh và chuyển mọi ngoại lệ không lường trước thành thông báo lỗi trên GUI."""
        try:
            func(*args)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._notify(f"[!] Error while running {label}: {exc.__class__.__name__}: {exc}")

    @staticmethod
    def _strip_quotes(value: str) -> str:
        """Bỏ dấu ngoặc kép/đơn bao quanh tham số (VD đường dẫn file có dấu cách)."""
        value = (value or "").strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            # Chỉ bóc cặp ngoặc ngoài cùng, KHÔNG xử lý escape để giữ nguyên dấu '\' của đường dẫn Windows.
            return value[1:-1].strip()
        return value
