"""
[THÀNH VIÊN C] - Giao diện người dùng chính bằng PySide6 (Thread 1 - Main Thread).
Giải quyết triệt để bài toán "Typing while messages arrive":
- Khung hiển thị lịch sử chat (QTextEdit read-only) và ô nhập văn bản (QLineEdit) tách biệt hoàn toàn.
- Mọi dữ liệu từ các luồng UDP/TCP đi qua AppSignals (QueuedConnection) nên không bao giờ làm vỡ chữ đang gõ.

Bố cục:
+--------------------+---------------------------------------------------+
| Quan  TCP:5001     | Chatting with Minh            192.168.1.12:5002  [Leave] |
| [online v]         |---------------------------------------------------|
|--------------------| 10:01:02 [Minh] Hi                                |
| ONLINE USERS (3)   | 10:01:05 [Quan] Hello                             |
| ● 1. Minh      (2) | [*] Huy is now online                             |
| ● 2. Lan (away)    |---------------------------------------------------|
| ● 3. Huy           | [slides.pdf -> Minh: 45%] (QProgressBar)          |
|                    | [ message input ..................] [Send] [File] |
+--------------------+---------------------------------------------------+
"""

import html
import time
from typing import Dict, List, Optional, Set, Tuple

from PySide6.QtCore import QSize, Qt, QTimer, Slot
from PySide6.QtGui import QCloseEvent, QColor, QFont, QKeyEvent, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.models import ChatMessage, PeerInfo
from core.shared_state import SharedState
from ui.command_parser import SELF_SENDER_ID, CommandParser
from ui.qt_signals import AppSignals

TEXT_COLOR = "#2c3e50"
PLACEHOLDER_COLOR = "#95a5a6"
STATUS_COLORS = {"online": "#2ecc71", "away": "#f39c12"}
OFFLINE_COLOR = "#95a5a6"
SELF_COLOR = "#2471a3"
PEER_COLOR = "#1e8449"
SYSTEM_COLOR = "#7f8c8d"
ERROR_COLOR = "#c0392b"
MAX_CHAT_BLOCKS = 5000          # Giới hạn số dòng giữ lại trong khung chat để tránh tốn RAM
PROGRESS_HIDE_DELAY_MS = 2000   # Ẩn thanh tiến độ sau khi lượt truyền cuối cùng kết thúc
INPUT_HISTORY_LIMIT = 100

STYLESHEET = """
QMainWindow, QWidget#centralWidget { background: #f4f6f8; color: #2c3e50; }
QWidget#sidebar { background: #ffffff; border-right: 1px solid #dfe3e8; color: #2c3e50; }
QLabel { color: #2c3e50; }
QLabel#myNameLabel { font-size: 16px; font-weight: bold; color: #2c3e50; }
QLabel#myPortLabel, QLabel#chatSubLabel, QLabel#hintLabel { color: #7f8c8d; }
QLabel#sectionLabel { color: #7f8c8d; font-weight: bold; letter-spacing: 1px; margin-top: 8px; }
QLabel#chatHeaderLabel { font-size: 15px; font-weight: bold; color: #2c3e50; }
QListWidget#peerList { border: none; background: transparent; outline: 0; color: #2c3e50; }
QListWidget#peerList::item { border-radius: 6px; margin: 1px 0; color: #2c3e50; }
QListWidget#peerList::item:hover { background: #eef3f8; }
QListWidget#peerList::item:selected { background: #d6eaf8; color: #2c3e50; }
QLabel#unreadBadge {
    background: #e74c3c; color: white; border-radius: 7px;
    padding: 1px 6px; font-weight: bold; min-width: 8px;
}
QTextEdit#chatDisplay {
    background: #ffffff; color: #2c3e50;
    selection-background-color: #3498db; selection-color: #ffffff;
    border: 1px solid #dfe3e8; border-radius: 8px; padding: 6px;
}
QLineEdit#messageInput {
    background: #ffffff; color: #2c3e50;
    selection-background-color: #3498db; selection-color: #ffffff;
    border: 1px solid #c8d0d8; border-radius: 6px; padding: 7px;
}
QLineEdit#messageInput:focus { border: 1px solid #3498db; color: #2c3e50; }
QPushButton {
    background: #3498db; color: white; border: none; border-radius: 6px; padding: 7px 14px;
}
QPushButton:hover { background: #2e86c1; }
QPushButton:disabled { background: #bdc3c7; color: #ffffff; }
QPushButton#leaveButton { background: #e74c3c; }
QPushButton#leaveButton:hover { background: #cb4335; }
QPushButton#leaveButton:disabled { background: #bdc3c7; color: #ffffff; }
QProgressBar {
    border: 1px solid #c8d0d8; border-radius: 6px; background: #ffffff; color: #2c3e50;
    text-align: center; height: 18px;
}
QProgressBar::chunk { background: #2ecc71; border-radius: 5px; }
QComboBox {
    padding: 4px 8px; border: 1px solid #c8d0d8; border-radius: 6px;
    background: #ffffff; color: #2c3e50;
}
QComboBox QAbstractItemView {
    background: #ffffff; color: #2c3e50;
    selection-background-color: #d6eaf8; selection-color: #2c3e50;
}
QToolTip {
    background: #ffffff; color: #2c3e50; border: 1px solid #c8d0d8;
}
"""


class HistoryLineEdit(QLineEdit):
    """Ô nhập liệu có lịch sử lệnh: phím Up/Down để gọi lại các dòng đã gõ (giống terminal)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._history: List[str] = []
        self._cursor = 0
        self._draft = ""

    def remember(self, text: str) -> None:
        if text and (not self._history or self._history[-1] != text):
            self._history.append(text)
            del self._history[:-INPUT_HISTORY_LIMIT]
        self._cursor = len(self._history)
        self._draft = ""

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - tên hàm của Qt
        if event.key() == Qt.Key_Up and self._history:
            if self._cursor == len(self._history):
                self._draft = self.text()
            self._cursor = max(0, self._cursor - 1)
            self.setText(self._history[self._cursor])
            return
        if event.key() == Qt.Key_Down and self._history:
            self._cursor = min(len(self._history), self._cursor + 1)
            self.setText(self._draft if self._cursor == len(self._history) else self._history[self._cursor])
            return
        super().keyPressEvent(event)


class PeerItemWidget(QWidget):
    """Một dòng trên Sidebar: chấm màu trạng thái, số thứ tự + tên, địa chỉ và badge số tin chưa đọc."""

    def __init__(self, index: int, peer: PeerInfo, unread: int, is_active: bool) -> None:
        super().__init__()
        self.setAttribute(Qt.WA_TransparentForMouseEvents)  # để click đi xuống QListWidget

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(8)

        color = STATUS_COLORS.get(peer.status, OFFLINE_COLOR)
        dot = QLabel()
        dot.setFixedSize(10, 10)
        dot.setStyleSheet(f"background: {color}; border-radius: 5px;")
        dot.setToolTip(peer.status)
        layout.addWidget(dot, 0, Qt.AlignVCenter)

        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        name_label = QLabel(f"{index}. {peer.name}")
        name_label.setTextFormat(Qt.PlainText)
        name_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        name_label.setStyleSheet(f"color: {TEXT_COLOR};")
        name_font = name_label.font()
        name_font.setBold(is_active or unread > 0)
        name_label.setFont(name_font)
        status_text = f" \u00b7 {peer.status}" if peer.status != "online" else ""
        addr_label = QLabel(f"{peer.ip}:{peer.tcp_port}{status_text}")
        addr_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        addr_label.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        text_box.addWidget(name_label)
        text_box.addWidget(addr_label)
        layout.addLayout(text_box, 1)

        if is_active:
            chatting = QLabel("chat")
            chatting.setStyleSheet(
                "background: #3498db; color: white; border-radius: 7px; padding: 1px 6px; font-size: 10px;"
            )
            chatting.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            chatting.setToolTip("Current chat")
            layout.addWidget(chatting, 0, Qt.AlignVCenter)

        self.badge = QLabel("99+" if unread > 99 else str(unread))
        self.badge.setObjectName("unreadBadge")
        self.badge.setAlignment(Qt.AlignCenter)
        self.badge.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.badge.setVisible(unread > 0)
        layout.addWidget(self.badge, 0, Qt.AlignVCenter)


class MainWindow(QMainWindow):
    """
    Cửa sổ chính của ứng dụng LAN Chat & File Sharing (PySide6).
    Chỉ đọc SharedState và nhận sự kiện qua AppSignals; mọi hành động của người dùng
    (gõ lệnh, click, chọn file, đổi trạng thái) đều được quy về chuỗi lệnh và chuyển cho CommandParser,
    nhờ vậy thao tác chuột và gõ lệnh luôn cho kết quả giống hệt nhau.
    """

    def __init__(
        self,
        shared_state: SharedState,
        command_parser: CommandParser,
        signals: AppSignals,
    ) -> None:
        super().__init__()
        self.shared_state = shared_state
        self.command_parser = command_parser
        self.signals = signals

        # Các thành phần UI chính (khởi tạo trong _setup_ui)
        self.peer_list_widget: QListWidget
        self.status_combo: QComboBox
        self.chat_header_label: QLabel
        self.chat_sub_label: QLabel
        self.chat_display: QTextEdit
        self.file_progress_bar: QProgressBar
        self.message_input: HistoryLineEdit
        self.send_btn: QPushButton
        self.send_file_btn: QPushButton
        self.leave_btn: QPushButton
        self.online_count_label: QLabel
        self.my_name_label: QLabel

        # Trạng thái riêng của giao diện (chỉ truy cập từ Main Thread)
        self._active_peer_id: Optional[str] = None
        self._pending_sidebar_peer_id: Optional[str] = None
        self._peer_names: Dict[str, str] = {}              # cache peer_id -> tên (kể cả khi peer đã offline)
        self._rendered_message_ids: Set[int] = set()       # chống hiển thị trùng 1 tin nhắn
        self._transfers: Dict[Tuple[str, str], int] = {}   # (peer_id, filename) -> % đang truyền
        self._finished_transfers: Set[Tuple[str, str]] = set()
        self._syncing_status = False

        self._progress_hide_timer = QTimer(self)
        self._progress_hide_timer.setSingleShot(True)
        self._progress_hide_timer.timeout.connect(self._hide_progress_if_idle)

        self._setup_ui()
        self._connect_signals()
        self._apply_active_peer(None)
        self.on_peer_list_updated()
        self._show_welcome()

    # ------------------------------------------------------------------
    # Xây dựng giao diện
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """
        Khởi tạo bố cục (Layout) cho cửa sổ PySide6:
        - Cột trái (Sidebar): Thông tin bản thân, hộp chọn trạng thái (online/away), danh sách Online Peers.
        - Cột phải (Main Chat Area): Tiêu đề người đang chat, vùng lịch sử tin nhắn, thanh tiến độ truyền file,
          và thanh nhập lệnh/tin nhắn ở dưới cùng.
        """
        my_name, my_port, my_status = self.shared_state.get_my_info()
        self.resize(980, 640)
        self.setMinimumSize(720, 460)
        self._apply_light_palette()
        self.setStyleSheet(STYLESHEET)
        base_font = QFont("Segoe UI", 10)
        self.setFont(base_font)

        central_widget = QWidget(self)
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        main_layout.addWidget(splitter)

        # --- Cột trái: Thông tin bản thân & Danh sách Peers ---
        left_panel = QWidget()
        left_panel.setObjectName("sidebar")
        left_panel.setMinimumWidth(220)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)

        self.my_name_label = QLabel(my_name)
        self.my_name_label.setObjectName("myNameLabel")
        left_layout.addWidget(self.my_name_label)
        port_label = QLabel(f"TCP port {my_port}")
        port_label.setObjectName("myPortLabel")
        left_layout.addWidget(port_label)

        self.status_combo = QComboBox()
        self.status_combo.addItem("\u25cf online", "online")
        self.status_combo.addItem("\u25cf away", "away")
        self.status_combo.setToolTip("Your presence status (same as /status <online|away>)")
        self._set_combo_status(my_status)
        left_layout.addWidget(self.status_combo)

        self.online_count_label = QLabel("ONLINE USERS (0)")
        self.online_count_label.setObjectName("sectionLabel")
        left_layout.addWidget(self.online_count_label)

        self.peer_list_widget = QListWidget()
        self.peer_list_widget.setObjectName("peerList")
        self.peer_list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.peer_list_widget.setToolTip("Click a user to open a chat (same as /chat <number>)")
        left_layout.addWidget(self.peer_list_widget, 1)

        hint = QLabel("Click a user to chat \u2022 /help for commands")
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        left_layout.addWidget(hint)
        splitter.addWidget(left_panel)

        # --- Cột phải: Khung Chat, Thanh Progress & Ô nhập liệu ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)

        header_layout = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(0)
        self.chat_header_label = QLabel()
        self.chat_header_label.setObjectName("chatHeaderLabel")
        self.chat_sub_label = QLabel()
        self.chat_sub_label.setObjectName("chatSubLabel")
        header_text.addWidget(self.chat_header_label)
        header_text.addWidget(self.chat_sub_label)
        header_layout.addLayout(header_text, 1)
        self.leave_btn = QPushButton("Leave (/leave)")
        self.leave_btn.setObjectName("leaveButton")
        self.leave_btn.setToolTip("Close the current chat")
        header_layout.addWidget(self.leave_btn)
        right_layout.addLayout(header_layout)

        self.chat_display = QTextEdit()
        self.chat_display.setObjectName("chatDisplay")
        self.chat_display.setReadOnly(True)
        self.chat_display.setFocusPolicy(Qt.ClickFocus)
        self.chat_display.document().setMaximumBlockCount(MAX_CHAT_BLOCKS)
        right_layout.addWidget(self.chat_display, 1)

        self.file_progress_bar = QProgressBar()
        self.file_progress_bar.setRange(0, 100)
        self.file_progress_bar.setValue(0)
        self.file_progress_bar.setVisible(False)
        right_layout.addWidget(self.file_progress_bar)

        input_layout = QHBoxLayout()
        self.message_input = HistoryLineEdit()
        self.message_input.setObjectName("messageInput")
        self.message_input.setPlaceholderText(
            "Type a message, or a command (/list, /chat, /send, /status, /leave, /help, /quit)..."
        )
        self.message_input.setClearButtonEnabled(True)
        self.send_btn = QPushButton("Send")
        self.send_btn.setDefault(True)
        self.send_file_btn = QPushButton("Send File...")
        self.send_file_btn.setToolTip("Pick a file and send it to the current chat partner (/send <file>)")
        input_layout.addWidget(self.message_input, 1)
        input_layout.addWidget(self.send_btn)
        input_layout.addWidget(self.send_file_btn)
        right_layout.addLayout(input_layout)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([250, 730])

        self.message_input.ensurePolished()
        input_palette = self.message_input.palette()
        input_palette.setColor(QPalette.Base, QColor("#ffffff"))
        input_palette.setColor(QPalette.Text, QColor(TEXT_COLOR))
        input_palette.setColor(QPalette.PlaceholderText, QColor(PLACEHOLDER_COLOR))
        self.message_input.setPalette(input_palette)
        self.message_input.setFocus()

    def _connect_signals(self) -> None:
        """
        Kết nối các sự kiện nút bấm trên GUI và các tín hiệu từ `self.signals` (AppSignals) vào các Slot xử lý.
        Các tín hiệu đến từ luồng nền sẽ tự động dùng QueuedConnection (Qt.AutoConnection).
        """
        self.signals.peer_list_updated.connect(self.on_peer_list_updated)
        self.signals.system_notification.connect(self.on_system_notification)
        self.signals.chat_message_received.connect(self.on_chat_message_received)
        self.signals.file_progress_updated.connect(self.on_file_progress_updated)
        self.signals.peer_disconnected.connect(self.on_peer_disconnected)
        self.signals.active_chat_changed.connect(self.on_active_chat_changed)
        self.signals.my_status_changed.connect(self.on_my_status_changed)

        self.message_input.returnPressed.connect(self._on_submit_input)
        self.send_btn.clicked.connect(self._on_submit_input)
        self.send_file_btn.clicked.connect(self._on_send_file_clicked)
        self.leave_btn.clicked.connect(self._on_leave_clicked)
        self.peer_list_widget.itemClicked.connect(self._on_peer_item_activated)
        self.peer_list_widget.itemActivated.connect(self._on_peer_item_activated)  # phím Enter
        self.status_combo.currentIndexChanged.connect(self._on_status_combo_changed)

    # ------------------------------------------------------------------
    # Hành động của người dùng -> CommandParser
    # ------------------------------------------------------------------

    @Slot()
    def _on_submit_input(self) -> None:
        """
        Lấy chuỗi từ `self.message_input`, xóa trống ô nhập và chuyển cho `self.command_parser.handle_user_input()`.
        """
        text = self.message_input.text()
        if not text.strip():
            return
        self.message_input.remember(text.strip())
        self.message_input.clear()
        self.command_parser.handle_user_input(text)
        self.message_input.setFocus()

    @Slot(QListWidgetItem)
    def _on_peer_item_activated(self, item: QListWidgetItem) -> None:
        """
        Click (hoặc Enter) vào một peer trên Sidebar tương đương lệnh `/chat <peer_id>`.
        Lệnh được hoãn bằng QTimer.singleShot(0): /chat sẽ dựng lại QListWidget (xóa item cũ),
        nếu chạy ngay trong lúc Qt còn đang xử lý sự kiện chuột trên chính item đó có thể gây crash.
        """
        peer_id = item.data(Qt.UserRole)
        if not peer_id or peer_id == self._active_peer_id or peer_id == self._pending_sidebar_peer_id:
            self.message_input.setFocus()
            return
        self._pending_sidebar_peer_id = peer_id
        QTimer.singleShot(0, lambda: self._open_chat_from_sidebar(peer_id))

    def _open_chat_from_sidebar(self, peer_id: str) -> None:
        self._pending_sidebar_peer_id = None
        if peer_id != self._active_peer_id:
            self.command_parser.handle_user_input(f"/chat {peer_id}")
            if self._active_peer_id != peer_id:
                # Kết nối thất bại -> đồng bộ lại vùng chọn trên Sidebar về đúng active peer
                self.on_peer_list_updated()
        self.message_input.setFocus()

    @Slot()
    def _on_send_file_clicked(self) -> None:
        """Mở QFileDialog chọn file rồi chuyển thành lệnh `/send "<đường dẫn>"`."""
        if self._active_peer_id is None:
            self.on_system_notification("[!] No active chat. Select a user first, then send a file.")
            return
        filepath, _ = QFileDialog.getOpenFileName(self, "Choose a file to send", "", "All files (*)")
        if filepath:
            self.command_parser.handle_user_input(f'/send "{filepath}"')
        self.message_input.setFocus()

    @Slot()
    def _on_leave_clicked(self) -> None:
        self.command_parser.handle_user_input("/leave")
        self.message_input.setFocus()

    @Slot(int)
    def _on_status_combo_changed(self, _index: int) -> None:
        """Đổi trạng thái bằng ComboBox tương đương lệnh `/status <online|away>`."""
        if self._syncing_status:
            return
        status = self.status_combo.currentData()
        self.command_parser.handle_user_input(f"/status {status}")
        self.message_input.setFocus()

    # ------------------------------------------------------------------
    # Slots nhận sự kiện từ AppSignals
    # ------------------------------------------------------------------

    @Slot()
    def on_peer_list_updated(self) -> None:
        """
        Slot cập nhật lại danh sách người dùng trên Sidebar kèm trạng thái (online/away) và số tin chưa đọc (unread).
        Thứ tự hiển thị trùng với `get_online_peers()` nên số thứ tự khớp với `/list` và `/chat <number>`.
        """
        peers = self.shared_state.get_online_peers()
        scroll_value = self.peer_list_widget.verticalScrollBar().value()

        self.peer_list_widget.setUpdatesEnabled(False)
        self.peer_list_widget.clear()
        for index, peer in enumerate(peers, start=1):
            self._peer_names[peer.peer_id] = peer.name
            is_active = peer.peer_id == self._active_peer_id
            unread = 0 if is_active else self.shared_state.get_unread_count(peer.peer_id)

            item = QListWidgetItem()
            item.setData(Qt.UserRole, peer.peer_id)
            item.setToolTip(
                f"{peer.name}\n{peer.ip}:{peer.tcp_port}\nStatus: {peer.status}"
                + (f"\nUnread: {unread}" if unread else "")
            )
            row_widget = PeerItemWidget(index, peer, unread, is_active)
            # Đặt chiều rộng = 0 để QListWidget ép widget vừa khít viewport, không hiện thanh cuộn ngang
            item.setSizeHint(QSize(0, max(44, row_widget.sizeHint().height())))
            self.peer_list_widget.addItem(item)
            self.peer_list_widget.setItemWidget(item, row_widget)
            item.setSelected(is_active)
        self.peer_list_widget.setUpdatesEnabled(True)
        self.peer_list_widget.verticalScrollBar().setValue(scroll_value)

        self.online_count_label.setText(f"ONLINE USERS ({len(peers)})")
        self._refresh_chat_header(peers)

    @Slot(str)
    def on_system_notification(self, text: str) -> None:
        """
        Slot hiển thị dòng thông báo hệ thống (VD: `[*] New message from Huy (1 unread)`) lên `self.chat_display`.
        Chỉ ghi vào QTextEdit, không đụng tới QLineEdit nên chữ đang gõ và vị trí con trỏ được giữ nguyên.
        """
        if not text:
            return
        color = ERROR_COLOR if text.lstrip().startswith("[!]") else SYSTEM_COLOR
        self._append_html(f'<span style="color:{color};">{self._escape_multiline(text)}</span>', monospace=True)

    @Slot(str, object)
    def on_chat_message_received(self, peer_id: str, message: object) -> None:
        """
        Slot xử lý khi có tin nhắn mới đến:
        - Nếu `peer_id` đang là `active_chat`: Hiển thị ngay nội dung tin nhắn lên `self.chat_display`.
        - Nếu `peer_id` KHÔNG phải `active_chat`: Cập nhật badge số lượng unread trên Sidebar
          (dòng thông báo "[*] New message from X (n unread)" do Thread 5 của Thành viên B phát).
        """
        if peer_id == self._active_peer_id:
            if id(message) in self._rendered_message_ids:
                return  # đã được vẽ lúc chuyển cuộc trò chuyện (tín hiệu tới trễ trong hàng đợi)
            self._rendered_message_ids.add(id(message))
            self._append_html(self._format_message(message))
            return

        self.on_peer_list_updated()
        if not self.isActiveWindow():
            QApplication.alert(self)  # nháy biểu tượng trên taskbar để báo có tin mới

    @Slot(str, str, int)
    def on_file_progress_updated(self, peer_id: str, filename: str, percentage: int) -> None:
        """
        Slot cập nhật thanh tiến độ `self.file_progress_bar` khi đang gửi hoặc nhận file.
        Hỗ trợ nhiều lượt truyền song song: thanh hiển thị lượt cập nhật gần nhất và số lượt còn lại.
        """
        key = (peer_id, filename)
        peer_name = self._peer_display_name(peer_id)

        if percentage < 0:
            self._transfers.pop(key, None)
            self._show_progress(f"{filename} \u2194 {peer_name}: failed", 0)
        elif percentage >= 100:
            was_running = self._transfers.pop(key, None) is not None
            if was_running or key not in self._finished_transfers:
                self._finished_transfers.add(key)
                self.on_system_notification(f"[*] {filename} \u2194 {peer_name} ... 100%  Done.")
            self._show_progress(f"{filename} \u2194 {peer_name}: 100% Done", 100)
        else:
            self._finished_transfers.discard(key)
            self._transfers[key] = percentage
            others = len(self._transfers) - 1
            extra = f"   (+{others} more)" if others > 0 else ""
            self._show_progress(f"{filename} \u2194 {peer_name}: {percentage}%{extra}", percentage)

        if self._transfers:
            self._progress_hide_timer.stop()
        else:
            self._progress_hide_timer.start(PROGRESS_HIDE_DELAY_MS)

    @Slot(str, str)
    def on_peer_disconnected(self, peer_id: str, reason: str) -> None:
        """
        Slot xử lý khi peer ngắt kết nối đột ngột hoặc gửi `BYE|`:
        thông báo cho người dùng, hủy các lượt truyền file với peer đó và
        quay về trạng thái "chưa chọn người chat" nếu đang chat với peer này.
        """
        name = self._peer_display_name(peer_id)
        for key in [k for k in self._transfers if k[0] == peer_id]:
            self._transfers.pop(key, None)
        if not self._transfers and self.file_progress_bar.isVisible():
            self._progress_hide_timer.start(PROGRESS_HIDE_DELAY_MS)

        detail = f" ({reason})" if reason else ""
        self.on_system_notification(f"[*] {name} disconnected{detail}.")

        if peer_id == self._active_peer_id:
            self.shared_state.set_active_chat(None)
            self._apply_active_peer(None)
            self.on_system_notification("[*] Chat closed. Pick another user or type /list.")
        self.on_peer_list_updated()

    @Slot(object, object, int)
    def on_active_chat_changed(self, peer: Optional[PeerInfo], history: object, unread: int) -> None:
        """
        Slot vẽ lại khung chat khi đổi cuộc trò chuyện (/chat, click Sidebar, /leave):
        xóa khung, in toàn bộ lịch sử của peer mới và chèn vạch "n unread" trước các tin chưa đọc.
        """
        self.chat_display.clear()
        self._rendered_message_ids.clear()
        self._apply_active_peer(peer)

        if peer is None:
            self._show_welcome()
            return

        messages = list(history or [])
        first_unread = len(messages) - unread if 0 < unread <= len(messages) else None
        if not messages:
            self.on_system_notification(f"[*] This is the beginning of your chat with {peer.name}.")
        for index, message in enumerate(messages):
            if index == first_unread:
                self._append_html(
                    f'<span style="color:{ERROR_COLOR};">\u2500\u2500\u2500\u2500  {unread} unread  \u2500\u2500\u2500\u2500</span>'
                )
            self._rendered_message_ids.add(id(message))
            self._append_html(self._format_message(message))

    @Slot(str)
    def on_my_status_changed(self, status: str) -> None:
        """Đồng bộ ComboBox và tiêu đề cửa sổ khi trạng thái đổi bằng lệnh /status."""
        self._set_combo_status(status)
        self._update_window_title()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - tên hàm của Qt
        """
        Bắt sự kiện đóng cửa sổ (nút X) để dọn dẹp các luồng UDP/TCP tương tự lệnh `/quit`.
        """
        self._progress_hide_timer.stop()
        self.command_parser.shutdown()
        event.accept()

    # ------------------------------------------------------------------
    # Tiện ích hiển thị
    # ------------------------------------------------------------------

    def _apply_light_palette(self) -> None:
        """
        Đặt bảng màu (QPalette) sáng nhất quán để khi Windows bật Dark Mode,
        chữ và placeholder không bị biến thành màu trắng trùng với nền trắng.
        """
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#f4f6f8"))
        palette.setColor(QPalette.WindowText, QColor(TEXT_COLOR))
        palette.setColor(QPalette.Base, QColor("#ffffff"))
        palette.setColor(QPalette.AlternateBase, QColor("#f4f6f8"))
        palette.setColor(QPalette.Text, QColor(TEXT_COLOR))
        palette.setColor(QPalette.PlaceholderText, QColor(PLACEHOLDER_COLOR))
        palette.setColor(QPalette.Button, QColor("#ffffff"))
        palette.setColor(QPalette.ButtonText, QColor(TEXT_COLOR))
        palette.setColor(QPalette.Highlight, QColor("#3498db"))
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        palette.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
        palette.setColor(QPalette.ToolTipText, QColor(TEXT_COLOR))
        self.setPalette(palette)
        app = QApplication.instance()
        if app is not None:
            app.setPalette(palette)

    def _apply_active_peer(self, peer: Optional[PeerInfo]) -> None:
        """Cập nhật biến trạng thái, tiêu đề khung chat và các nút phụ thuộc vào việc đang chat hay không."""
        self._active_peer_id = peer.peer_id if peer else None
        if peer is not None:
            self._peer_names[peer.peer_id] = peer.name
        self.leave_btn.setEnabled(peer is not None)
        self.send_file_btn.setEnabled(peer is not None)
        self._refresh_chat_header()
        self._update_window_title()

    def _refresh_chat_header(self, peers: Optional[List[PeerInfo]] = None) -> None:
        if self._active_peer_id is None:
            self.chat_header_label.setText("No active chat")
            self.chat_sub_label.setText("Click a user on the left, or type /chat <name|number>")
            return
        if peers is None:
            peers = self.shared_state.get_online_peers()
        peer = next((p for p in peers if p.peer_id == self._active_peer_id), None)
        name = self._peer_display_name(self._active_peer_id)
        self.chat_header_label.setText(f"Chatting with {name}")
        if peer is None:
            self.chat_sub_label.setText(f"{self._active_peer_id} \u00b7 no presence broadcast (may be offline)")
        else:
            self.chat_sub_label.setText(
                f'{peer.ip}:{peer.tcp_port} \u00b7 <span style="color:{STATUS_COLORS.get(peer.status, OFFLINE_COLOR)}">'
                f"\u25cf</span> {peer.status}"
            )

    def _update_window_title(self) -> None:
        my_name, my_port, my_status = self.shared_state.get_my_info()
        title = f"LAN Chat & File Sharing - {my_name} (TCP:{my_port}) - {self.status_combo.currentData() or my_status}"
        if self._active_peer_id is not None:
            title += f" - chatting with {self._peer_display_name(self._active_peer_id)}"
        self.setWindowTitle(title)

    def _set_combo_status(self, status: str) -> None:
        index = self.status_combo.findData(status)
        if index < 0:
            return
        self._syncing_status = True
        try:
            self.status_combo.setCurrentIndex(index)
        finally:
            self._syncing_status = False

    def _show_welcome(self) -> None:
        my_name, my_port, _ = self.shared_state.get_my_info()
        self.on_system_notification(
            f"[*] Welcome, {my_name}! You are listening on TCP port {my_port}.\n"
            "[*] Click a user on the left (or type /list then /chat <name|number>) to start chatting.\n"
            "[*] Type /help to see all commands."
        )

    def _show_progress(self, text: str, value: int) -> None:
        self.file_progress_bar.setFormat(text)
        self.file_progress_bar.setValue(max(0, min(100, value)))
        self.file_progress_bar.setVisible(True)

    @Slot()
    def _hide_progress_if_idle(self) -> None:
        if not self._transfers:
            self.file_progress_bar.setVisible(False)
            self.file_progress_bar.setValue(0)

    def _peer_display_name(self, peer_id: str) -> str:
        return self._peer_names.get(peer_id, peer_id)

    def _append_html(self, html_text: str, monospace: bool = False) -> None:
        """
        Thêm một đoạn vào cuối khung chat. Chỉ tự cuộn xuống nếu người dùng đang ở cuối
        (không giật màn hình khi họ đang kéo lên đọc tin cũ).
        """
        scrollbar = self.chat_display.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum() - 4
        if monospace:
            html_text = f"<span style=\"font-family:Consolas,'Courier New',monospace;\">{html_text}</span>"
        self.chat_display.append(html_text)
        if at_bottom:
            scrollbar.setValue(scrollbar.maximum())

    def _format_message(self, message: object) -> str:
        if not isinstance(message, ChatMessage):
            return html.escape(str(message))
        timestamp = time.strftime("%H:%M:%S", time.localtime(message.timestamp))
        content = self._escape_multiline(message.content)
        if message.is_system:
            return f'<span style="color:{SYSTEM_COLOR};">{timestamp} [*] {content}</span>'
        color = SELF_COLOR if message.sender_id == SELF_SENDER_ID else PEER_COLOR
        return (
            f'<span style="color:#aab7b8;">{timestamp}</span> '
            f'<b style="color:{color};">[{html.escape(message.sender_name)}]</b> '
            f'<span style="color:{TEXT_COLOR};">{content}</span>'
        )

    @staticmethod
    def _escape_multiline(text: str) -> str:
        """Escape HTML, giữ xuống dòng và khoảng trắng liên tiếp (để bảng /list thẳng cột)."""
        escaped = html.escape(text)
        escaped = escaped.replace("  ", "&nbsp;&nbsp;")
        return escaped.replace("\n", "<br>")
