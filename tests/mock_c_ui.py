"""
Script kiểm thử độc lập dành cho [THÀNH VIÊN C].
Dùng để bật giao diện PySide6 với dữ liệu Peer giả lập (Mock Peers) và một luồng nền thật
(threading.Thread) bắn tin nhắn tự động mỗi 1 giây nhằm kiểm chứng:
- Khi đang gõ dở câu dài trong ô Input, tin nhắn từ người khác đổ về không làm vỡ chữ hay mất con trỏ.
- Các lệnh /list, /chat, /send, /status, /leave, /help, /quit hoạt động đúng.

Không cần phần của Thành viên A/B: script tự cung cấp
- MockSharedState  : hiện thực đầy đủ hợp đồng SharedState (overview.md 4.1) bằng RLock trong bộ nhớ.
- MockUDPService   : ghi lại các lần start/stop/send_immediate_broadcast.
- MockTCPManager   : giả lập connect/send/disconnect; gửi file chạy trên luồng riêng và phát % tiến độ.
- FakeNetworkThread: luồng nền giả làm Thread 3/5 (peer vào/ra, đổi status, tin nhắn đến, peer ngắt kết nối).

Cách chạy:
    python -m tests.mock_c_ui              # mở cửa sổ để test bằng tay (có dữ liệu giả chạy liên tục)
    python -m tests.mock_c_ui --selftest   # chạy bộ kiểm thử tự động (không cần màn hình), in PASS/FAIL
"""

import argparse
import os
import random
import sys
import tempfile
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

if "--selftest" in sys.argv:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from core.models import ChatMessage, PeerInfo  # noqa: E402
from core.shared_state import SharedState  # noqa: E402
from ui.command_parser import SELF_SENDER_ID, CommandParser  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402
from ui.qt_signals import AppSignals  # noqa: E402

MOCK_PEERS = [
    ("Minh", "192.168.1.12", 5002, "online"),
    ("Lan", "192.168.1.15", 5003, "away"),
    ("Huy", "192.168.1.20", 5004, "online"),
    ("Ghost", "192.168.1.99", 5099, "online"),  # luôn từ chối kết nối TCP -> test lỗi "peer offline"
]
REFUSING_PEERS = {"Ghost"}
RANDOM_LINES = [
    "Hi, are you ready for the demo?",
    "Send me the slides please",
    "Xin chào, tiếng Việt có dấu vẫn hiển thị đúng chứ?",
    "the router config is done",
    "sending the screenshot now",
    "ok, which part?",
    "Ping! Did you receive the file?",
    "Let's test a much longer message to see that word wrapping in the chat area works fine.",
]


# ----------------------------------------------------------------------
# Mock của Thành viên A
# ----------------------------------------------------------------------


class MockSharedState(SharedState):
    """Hiện thực đầy đủ hợp đồng SharedState trong bộ nhớ (chỉ phục vụ test giao diện)."""

    def set_my_status(self, status: str) -> None:
        if status not in ("online", "away"):
            raise ValueError(status)
        with self._lock:
            self.my_status = status

    def get_my_info(self) -> Tuple[str, int, str]:
        with self._lock:
            return (self.my_name, self.my_tcp_port, self.my_status)

    def upsert_peer(self, name: str, ip: str, tcp_port: int, status: str) -> Optional[str]:
        with self._lock:
            peer_id = f"{ip}:{tcp_port}"
            existing = self.peers.get(peer_id)
            if existing is None:
                self.peers[peer_id] = PeerInfo(name, ip, tcp_port, status)
                return "joined"
            changed = existing.status != status or existing.name != name
            existing.name, existing.status, existing.last_seen = name, status, time.time()
            return "status_changed" if changed else None

    def remove_peer(self, peer_id: str) -> Optional[PeerInfo]:
        with self._lock:
            return self.peers.pop(peer_id, None)

    def remove_expired_peers(self, timeout_sec: float = 10.0) -> List[PeerInfo]:
        return []

    def get_online_peers(self) -> List[PeerInfo]:
        with self._lock:
            return list(self.peers.values())

    def find_peer(self, target: str) -> Optional[PeerInfo]:
        with self._lock:
            peers = list(self.peers.values())
            if target.isdigit():
                index = int(target) - 1
                return peers[index] if 0 <= index < len(peers) else None
            if target in self.peers:
                return self.peers[target]
            return next((p for p in peers if p.name.lower() == target.lower()), None)

    def set_active_chat(self, peer_id: Optional[str]) -> List[ChatMessage]:
        with self._lock:
            self.active_chat_peer_id = peer_id
            if peer_id is None:
                return []
            self.unread_counts[peer_id] = 0
            return list(self.chat_histories.get(peer_id, []))

    def get_active_chat(self) -> Optional[PeerInfo]:
        with self._lock:
            if self.active_chat_peer_id is None:
                return None
            return self.peers.get(self.active_chat_peer_id)

    def append_message(self, peer_id: str, msg: ChatMessage) -> int:
        with self._lock:
            self.chat_histories.setdefault(peer_id, []).append(msg)
            if peer_id != self.active_chat_peer_id and msg.sender_id != SELF_SENDER_ID:
                self.unread_counts[peer_id] = self.unread_counts.get(peer_id, 0) + 1
            return self.unread_counts.get(peer_id, 0)

    def get_unread_count(self, peer_id: str) -> int:
        with self._lock:
            return self.unread_counts.get(peer_id, 0)


class MockUDPService:
    def __init__(self) -> None:
        self.calls: List[str] = []

    def start(self) -> None:
        self.calls.append("start")

    def stop(self) -> None:
        self.calls.append("stop")

    def send_immediate_broadcast(self) -> None:
        self.calls.append("broadcast")


# ----------------------------------------------------------------------
# Mock của Thành viên B
# ----------------------------------------------------------------------


class MockTCPManager:
    """Giả lập TCPConnectionManager: tự trả lời tin nhắn và truyền file trên luồng riêng (Thread 6)."""

    def __init__(self, shared_state: MockSharedState, signals: AppSignals, auto_reply: bool = True) -> None:
        self.shared_state = shared_state
        self.signals = signals
        self.auto_reply = auto_reply
        self.calls: List[Tuple[str, str]] = []
        self.fail_next_send = False
        self.raise_on_send = False
        self._stopped = threading.Event()

    def start_server(self) -> None:
        self.calls.append(("start_server", ""))

    def connect_to_peer(self, peer: PeerInfo) -> bool:
        self.calls.append(("connect", peer.peer_id))
        if peer.name in REFUSING_PEERS:
            self.signals.system_notification.emit(f"[!] Connection refused by {peer.ip}:{peer.tcp_port}")
            return False
        return True

    def send_text_message(self, peer_id: str, text: str) -> bool:
        self.calls.append(("send_text", peer_id))
        if self.raise_on_send:
            raise RuntimeError("simulated socket crash")
        if self.fail_next_send:
            self.fail_next_send = False
            return False
        if self.auto_reply:
            threading.Thread(target=self._reply_later, args=(peer_id, text), daemon=True).start()
        return True

    def send_file_async(self, peer_id: str, filepath: str) -> None:
        self.calls.append(("send_file", filepath))
        threading.Thread(target=self._fake_file_sender, args=(peer_id, filepath), daemon=True).start()

    def disconnect_peer(self, peer_id: str) -> None:
        self.calls.append(("disconnect", peer_id))

    def stop_all(self) -> None:
        self.calls.append(("stop_all", ""))
        self._stopped.set()

    def _reply_later(self, peer_id: str, text: str) -> None:
        if self._stopped.wait(0.8):
            return
        peer = next((p for p in self.shared_state.get_online_peers() if p.peer_id == peer_id), None)
        if peer is None:
            return
        deliver_message(self.shared_state, self.signals, peer, f"(auto-reply) I got: {text}")

    def _fake_file_sender(self, peer_id: str, filepath: str) -> None:
        """[Giả lập Thread 6] Phát tín hiệu tiến độ từ luồng nền, giống FileTransferService thật."""
        filename = os.path.basename(filepath)
        for percent in range(0, 101, 5):
            if self._stopped.wait(0.03):
                return
            self.signals.file_progress_updated.emit(peer_id, filename, percent)


def deliver_message(shared_state: SharedState, signals: AppSignals, peer: PeerInfo, text: str) -> None:
    """Làm đúng việc Thread 5 (TCP Receiver) của Thành viên B sẽ làm khi nhận một khung MSG."""
    msg = ChatMessage(sender_name=peer.name, sender_id=peer.peer_id, content=text)
    unread = shared_state.append_message(peer.peer_id, msg)
    signals.chat_message_received.emit(peer.peer_id, msg)
    if unread > 0:
        signals.system_notification.emit(f"[*] New message from {peer.name} ({unread} unread)")
        signals.peer_list_updated.emit()


class FakeNetworkThread(threading.Thread):
    """Luồng nền giả lập lưu lượng mạng để test GUI bằng tay (Thread 3 + Thread 5 giả)."""

    def __init__(self, shared_state: MockSharedState, signals: AppSignals, interval: float = 1.0) -> None:
        super().__init__(name="FakeNetworkThread", daemon=True)
        self.shared_state = shared_state
        self.signals = signals
        self.interval = interval
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        tick = 0
        while not self._stop_event.wait(self.interval):
            tick += 1
            peers = [p for p in self.shared_state.get_online_peers() if p.name not in REFUSING_PEERS]
            if peers:
                deliver_message(self.shared_state, self.signals, random.choice(peers), random.choice(RANDOM_LINES))
            if tick % 5 == 0:  # Lan đổi trạng thái online <-> away
                lan = self.shared_state.find_peer("Lan")
                if lan is not None:
                    new_status = "online" if lan.status == "away" else "away"
                    self.shared_state.upsert_peer(lan.name, lan.ip, lan.tcp_port, new_status)
                    self.signals.peer_list_updated.emit()
            if tick % 8 == 0:  # Tuan vào / ra mạng
                tuan = self.shared_state.find_peer("Tuan")
                if tuan is None:
                    self.shared_state.upsert_peer("Tuan", "192.168.1.30", 5005, "online")
                    self.signals.system_notification.emit("[*] Tuan is now online")
                else:
                    self.shared_state.remove_peer(tuan.peer_id)
                    self.signals.system_notification.emit("[*] Tuan went offline")
                self.signals.peer_list_updated.emit()


# ----------------------------------------------------------------------
# Lắp ráp
# ----------------------------------------------------------------------


class MockApp:
    def __init__(self, app: QApplication, auto_reply: bool = True) -> None:
        self.app = app
        self.quit_calls = 0
        self.state = MockSharedState(my_name="Quan", my_tcp_port=5001)
        for name, ip, port, status in MOCK_PEERS:
            self.state.upsert_peer(name, ip, port, status)
        self.signals = AppSignals()
        self.udp = MockUDPService()
        self.tcp = MockTCPManager(self.state, self.signals, auto_reply=auto_reply)
        self.parser = CommandParser(self.state, self.udp, self.tcp, self.signals, on_quit_callback=self._on_quit)
        self.window = MainWindow(self.state, self.parser, self.signals)

    def _on_quit(self) -> None:
        self.quit_calls += 1
        self.app.quit()

    def peer(self, name: str) -> PeerInfo:
        peer = self.state.find_peer(name)
        assert peer is not None, name
        return peer


def run_interactive() -> int:
    app = QApplication(sys.argv[:1])
    mock = MockApp(app)
    network = FakeNetworkThread(mock.state, mock.signals)
    mock.window.show()
    network.start()
    print("[Mock Test C] Window opened. A background thread sends a message every second.")
    print("  - Type a long sentence slowly: incoming messages must not break your text or cursor.")
    print("  - Try: /list, /chat 1, /chat Ghost (refused), /send <file>, /status away, /leave, /help, /quit")
    exit_code = app.exec()
    network.stop()
    mock.parser.shutdown()
    return exit_code


# ----------------------------------------------------------------------
# Bộ kiểm thử tự động (headless)
# ----------------------------------------------------------------------


class SelfTest:
    def __init__(self) -> None:
        self.app = QApplication.instance() or QApplication(sys.argv[:1])
        self.mock = MockApp(self.app, auto_reply=False)
        self.window = self.mock.window
        self.results: List[Tuple[str, bool, str]] = []

    # --- tiện ích ---
    def pump(self, seconds: float = 0.05) -> None:
        end = time.time() + seconds
        while time.time() < end:
            self.app.processEvents()
            time.sleep(0.005)

    def wait_until(self, condition: Callable[[], bool], timeout: float = 3.0) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            self.app.processEvents()
            if condition():
                return True
            time.sleep(0.01)
        return condition()

    def display(self) -> str:
        return self.window.chat_display.toPlainText()

    def run_cmd(self, text: str) -> None:
        self.mock.parser.handle_user_input(text)
        self.pump()

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        self.results.append((name, bool(condition), detail))

    def emit_from_thread(self, func: Callable[[], None]) -> None:
        worker = threading.Thread(target=func, daemon=True)
        worker.start()
        worker.join(2)

    # --- kịch bản ---
    def run(self) -> int:
        state, tcp, udp, window = self.mock.state, self.mock.tcp, self.mock.udp, self.window
        minh, huy = self.mock.peer("Minh"), self.mock.peer("Huy")
        self.window.show()
        self.pump()

        self.check(
            "search bar uses English placeholder",
            "Search" in window.search_input.placeholderText()
            and "Tìm kiếm" not in window.search_input.placeholderText(),
            window.search_input.placeholderText(),
        )
        online_ids = [
            window.peer_list_widget.item(i).data(0x0100)
            for i in range(window.peer_list_widget.count())
            if window.peer_list_widget.item(i).data(0x0100)
        ]
        lan = self.mock.peer("Lan")
        self.check(
            "Online Users tab shows strictly online peers (excludes away)",
            len(online_ids) == 3 and lan.peer_id not in online_ids and window.online_users_btn.text() == "Online Users (3)",
            f"ids={online_ids} btn={window.online_users_btn.text()!r}",
        )
        window.all_chats_btn.click()
        self.pump()
        all_chat_ids_initial = [
            window.peer_list_widget.item(i).data(0x0100)
            for i in range(window.peer_list_widget.count())
            if window.peer_list_widget.item(i).data(0x0100)
        ]
        self.check(
            "All Chats tab initially empty before messaging",
            len(all_chat_ids_initial) == 0 and window.all_chats_btn.text() == "All Chats (0)",
            f"ids={all_chat_ids_initial} btn={window.all_chats_btn.text()!r}",
        )
        window.online_users_btn.click()
        self.pump()

        self.run_cmd("/help")
        self.check("/help lists every command", all(c in self.display() for c in
                   ("/list", "/chat", "/send", "/leave", "/status", "/help", "/quit")))

        self.run_cmd("/list")
        self.check("/list shows numbered users with IP and status",
                   "1. Minh" in self.display() and "192.168.1.15:5003" in self.display() and "away" in self.display())

        self.run_cmd("hello?")
        self.check("plain text without active chat -> warning", "[!] No active chat" in self.display())

        self.run_cmd("/chat")
        self.check("/chat without argument -> usage", "Usage: /chat" in self.display())

        self.run_cmd("/chat 1")
        self.check("/chat 1 opens chat with Minh", state.active_chat_peer_id == minh.peer_id
                   and "Chatting with Minh" in window.chat_header_label.text() and window.leave_btn.isEnabled())

        # Tin nhắn từ peer khác (Huy) đến từ LUỒNG NỀN -> unread + badge, không in vào khung chat của Minh
        self.emit_from_thread(lambda: (deliver_message(state, self.mock.signals, huy, "huy-msg-1"),
                                       deliver_message(state, self.mock.signals, huy, "huy-msg-2")))
        self.pump(0.2)
        badge_texts = [window.peer_list_widget.itemWidget(window.peer_list_widget.item(i)).badge.text()
                       for i in range(window.peer_list_widget.count())
                       if window.peer_list_widget.item(i).data(0x0100) == huy.peer_id]
        self.check("messages from non-active peer increase unread", state.get_unread_count(huy.peer_id) == 2)
        self.check("sidebar badge shows 2 for Huy", badge_texts == ["2"], str(badge_texts))
        self.check("non-active message not printed in chat", "huy-msg-1" not in self.display()
                   and "New message from Huy (2 unread)" in self.display())

        # Đang gõ dở thì tin nhắn đến -> ô input giữ nguyên chữ và vị trí con trỏ
        window.message_input.setText("you can che")
        window.message_input.setCursorPosition(7)
        self.emit_from_thread(lambda: [deliver_message(state, self.mock.signals, minh, f"minh-live-{i}") for i in range(20)])
        self.pump(0.3)
        self.check("typed text preserved while 20 messages arrive",
                   window.message_input.text() == "you can che" and window.message_input.cursorPosition() == 7,
                   f"{window.message_input.text()!r} @ {window.message_input.cursorPosition()}")
        self.check("active-chat messages shown immediately", "minh-live-19" in self.display())

        window.message_input.setText("Hello Minh, xin chào!")
        window._on_submit_input()
        self.pump()
        history = state.chat_histories.get(minh.peer_id, [])
        self.check("own message sent, stored as SELF and displayed",
                   ("send_text", minh.peer_id) in tcp.calls and history[-1].sender_id == SELF_SENDER_ID
                   and "[Quan] Hello Minh, xin chào!" in self.display() and window.message_input.text() == "")

        tcp.fail_next_send = True
        self.run_cmd("this will fail")
        self.check("failed send -> error, not stored", "Message not delivered" in self.display()
                   and state.chat_histories[minh.peer_id][-1].content != "this will fail")

        self.run_cmd("/chat Huy")
        self.check("/chat Huy switches and resets unread", state.active_chat_peer_id == huy.peer_id
                   and state.get_unread_count(huy.peer_id) == 0)
        self.check("switched chat shows history with unread separator",
                   "huy-msg-1" in self.display() and "2 unread" in self.display() and "minh-live-3" not in self.display())

        self.run_cmd("/chat huy")
        self.check("/chat same peer -> 'already chatting'", "already chatting with Huy" in self.display())

        self.run_cmd("/chat Ghost")
        self.check("/chat refused peer -> error, stays on Huy", "Could not connect to Ghost" in self.display()
                   and state.active_chat_peer_id == huy.peer_id)

        self.run_cmd("/chat Nobody")
        self.check("/chat unknown user -> not found", "'Nobody' not found" in self.display())

        broadcasts_before = udp.calls.count("broadcast")
        self.run_cmd("/status away")
        self.check("/status away updates state, combo and broadcasts once",
                   state.my_status == "away" and window.status_combo.currentData() == "away"
                   and udp.calls.count("broadcast") == broadcasts_before + 1)
        self.run_cmd("/status busy")
        self.check("/status invalid -> usage", "Usage: /status <online|away>" in self.display())
        window.status_combo.setCurrentIndex(window.status_combo.findData("online"))
        self.pump()
        self.check("status combo click == /status online", state.my_status == "online"
                   and udp.calls.count("broadcast") == broadcasts_before + 2)

        self.run_cmd("/send does_not_exist.bin")
        self.check("/send missing file -> error", "File not found: does_not_exist.bin" in self.display())

        with tempfile.NamedTemporaryFile("wb", suffix=" demo file.bin", delete=False) as tmp:
            tmp.write(os.urandom(300 * 1024))
            tmp_path = tmp.name
        try:
            self.run_cmd(f'/send "{tmp_path}"')
            self.check("/send quoted path with spaces starts transfer",
                       ("send_file", os.path.abspath(tmp_path)) in tcp.calls and "300.0 KB" in self.display())
            self.check("progress bar becomes visible", self.wait_until(window.file_progress_bar.isVisible, 2))
            self.check("transfer reaches 100% Done", self.wait_until(lambda: "100%  Done" in self.display(), 3))
            self.check("progress bar hides after completion",
                       self.wait_until(lambda: not window.file_progress_bar.isVisible(), 4))
        finally:
            os.remove(tmp_path)

        self.emit_from_thread(lambda: self.mock.signals.peer_disconnected.emit(huy.peer_id, "connection reset"))
        self.pump(0.2)
        self.check("active peer disconnect -> notice and chat closed",
                   "Huy disconnected (connection reset)" in self.display() and state.active_chat_peer_id is None
                   and window.chat_header_label.text() == "No active chat" and not window.send_file_btn.isEnabled())

        self.run_cmd("/leave")
        self.check("/leave without chat -> error", "You are not in a chat" in self.display())

        item = window.peer_list_widget.item(0)
        clicked_peer_id = item.data(0x0100)
        window._on_peer_item_activated(item)
        self.pump()
        self.check("click on sidebar == /chat", state.active_chat_peer_id == clicked_peer_id)

        self.run_cmd("/leave")
        self.check("/leave sends disconnect and resets chat", ("disconnect", minh.peer_id) in tcp.calls
                   and state.active_chat_peer_id is None and "Left the chat with Minh" in self.display())

        self.run_cmd("/foo bar")
        self.check("unknown command -> short help", "Unknown command: /foo" in self.display())

        self.run_cmd("/chat 1")
        tcp.raise_on_send = True
        print("(expected) a simulated RuntimeError traceback is printed below by the error guard:", file=sys.stderr)
        self.run_cmd("boom")
        tcp.raise_on_send = False
        self.check("exception in network layer is caught and shown",
                   "Error while running send message: RuntimeError" in self.display())

        # Kiểm thử tab All Chats (hiển thị tất cả người đã nhắn tin, tìm kiếm, xem lịch sử khi offline)
        window.all_chats_btn.click()
        self.pump(0.1)
        chat_ids = [
            window.peer_list_widget.item(i).data(0x0100)
            for i in range(window.peer_list_widget.count())
            if window.peer_list_widget.item(i).data(0x0100)
        ]
        self.check(
            "All Chats tab shows users with chat history",
            minh.peer_id in chat_ids and huy.peer_id in chat_ids and len(chat_ids) == 2
            and window.all_chats_btn.text() == "All Chats (2)",
            f"ids={chat_ids} btn={window.all_chats_btn.text()!r}",
        )

        window.search_input.setText("demo file.bin")
        self.pump()
        filtered_ids = [
            window.peer_list_widget.item(i).data(0x0100)
            for i in range(window.peer_list_widget.count())
            if window.peer_list_widget.item(i).data(0x0100)
        ]
        self.check(
            "search filters All Chats by last message preview",
            filtered_ids == [huy.peer_id],
            str(filtered_ids),
        )
        window.search_input.setText("xin chào")
        self.pump()
        filtered_minh = [
            window.peer_list_widget.item(i).data(0x0100)
            for i in range(window.peer_list_widget.count())
            if window.peer_list_widget.item(i).data(0x0100)
        ]
        self.check(
            "search filters All Chats by UTF-8 last message preview",
            filtered_minh == [minh.peer_id],
            str(filtered_minh),
        )
        window.search_input.clear()
        self.pump()

        # Giả lập Huy offline -> biến mất khỏi Online Users nhưng vẫn xem lại lịch sử read-only ở All Chats
        state.remove_peer(huy.peer_id)
        self.mock.signals.peer_list_updated.emit()
        self.pump(0.1)
        self.check(
            "offline peer removed from Online Users count but kept in All Chats",
            window.online_users_btn.text() == "Online Users (2)" and window.all_chats_btn.text() == "All Chats (2)",
            f"online={window.online_users_btn.text()!r} chats={window.all_chats_btn.text()!r}",
        )
        huy_item = next(
            (window.peer_list_widget.item(i) for i in range(window.peer_list_widget.count())
             if window.peer_list_widget.item(i).data(0x0100) == huy.peer_id),
            None,
        )
        self.check("offline conversation item found in All Chats", huy_item is not None)
        if huy_item is not None:
            window._on_peer_item_activated(huy_item)
            self.pump(0.1)
        self.check(
            "clicking offline peer in All Chats opens read-only history",
            "Chat history with Huy" in window.chat_header_label.text()
            and "huy-msg-1" in self.display()
            and not window.send_file_btn.isEnabled()
            and not window.leave_btn.isEnabled(),
            f"header={window.chat_header_label.text()!r}",
        )
        window.message_input.setText("can I still send?")
        window._on_submit_input()
        self.pump()
        self.check(
            "sending text while viewing offline history shows read-only warning",
            "Huy is currently offline" in self.display(),
        )

        self.run_cmd("/quit")
        window.close()
        self.pump()
        self.check("/quit stops UDP and TCP exactly once and quits",
                   udp.calls.count("stop") == 1 and [c for c, _ in tcp.calls].count("stop_all") == 1
                   and self.mock.quit_calls == 1, f"udp={udp.calls} quit={self.mock.quit_calls}")

        return self.report()

    def report(self) -> int:
        failed = 0
        for name, ok, detail in self.results:
            failed += not ok
            print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  -> {detail}" if not ok and detail else ""))
        print(f"\n{len(self.results) - failed}/{len(self.results)} checks passed.")
        return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Member C - PySide6 UI mock test")
    parser.add_argument("--selftest", action="store_true", help="run automated headless checks")
    args = parser.parse_args()
    if args.selftest:
        return SelfTest().run()
    return run_interactive()


if __name__ == "__main__":
    sys.exit(main())
