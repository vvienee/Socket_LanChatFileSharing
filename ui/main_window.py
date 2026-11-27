"""
[THÀNH VIÊN C] - Giao diện người dùng chính bằng PySide6 (Thread 1 - Main Thread).
Áp dụng thiết kế từ Figma "Messaging App UI (Community)" (Frames 1:146, 1:499, 55:19)
chuyển đổi sang bố cục Desktop 2 cột kèm các tính năng nâng cao:
- Bong bóng tin nhắn bo góc tròn thật sự (ChatBubbleWidget với border-radius 16px).
- Xóa tin nhắn ở phía mình & Thu hồi tin nhắn hai chiều qua TCP có thông báo như Messenger.
- Đổi Avatar cá nhân (chọn ảnh bất kỳ từ máy tính hoặc chọn từ 5 mẫu Avatar Figma).
- Bảng chọn Emoji (Emoji Picker Popup Grid) chèn nhanh biểu tượng cảm xúc vào ô nhập.
- Thanh tìm kiếm bạn bè theo Tên / IP:Port theo thời gian thực trên Sidebar.
- Lược bỏ các nút thừa (Micro, Video call, Chevron/3 chấm, Kính lúp tĩnh).
"""

import html
import os
import time
from typing import Callable, Dict, List, Optional, Set, Tuple

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, QTimer, Signal, Slot
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QColor,
    QContextMenuEvent,
    QFont,
    QIcon,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPalette,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from core.models import RECALL_PREFIX, ChatMessage, PeerInfo
from core.shared_state import SharedState
from ui.command_parser import SELF_SENDER_ID, CommandParser
from ui.qt_signals import AppSignals

# ------------------------------------------------------------------
# Figma Design Tokens ("Messaging App UI - Community", Nodes 1:146 & 1:499)
# ------------------------------------------------------------------
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

PRIMARY_BLUE = "#2f80ed"        # Figma: Blue 1
PRIMARY_BLUE_HOVER = "#1f6fd8"
PRIMARY_BLUE_LIGHT = "#eaf2fd"  # Figma: #2F80ED at 10% opacity (active row 1:217)
TEXT_COLOR = "#1b1a57"          # Figma: Text - Primary (#1B1A57)
TEXT_SECONDARY = "#4f5e7b"      # Figma: Text - Secondary (#4F5E7B)
PLACEHOLDER_COLOR = "#a1a1bc"   # Figma: Muted / Timestamp (#A1A1BC)
STATUS_COLORS = {"online": "#4ce417", "away": "#f2c94c"}
OFFLINE_COLOR = "#bdbdbd"
SELF_COLOR = "#ffffff"
PEER_COLOR = "#f2994a"          # Figma: Orange (#F2994A) for peer sender name (node 1:501)
BUBBLE_PEER_BG = "#f7f7f7"      # Figma: Incoming bubble surface (node 1:500)
BUBBLE_SELF_BG = "#2f80ed"      # Figma: Outgoing bubble surface (node 1:513)
SYSTEM_COLOR = "#4f5e7b"
ERROR_COLOR = "#eb5757"

AVATAR_FILES = [
    "avatar_1.png",
    "avatar_2.png",
    "avatar_3.png",
    "avatar_4.png",
    "avatar_5.png",
]
AVATAR_FALLBACK_COLORS = [
    "#2f80ed",
    "#f2994a",
    "#27ae60",
    "#9b51e0",
    "#eb5757",
]

EMOJI_LIST = [
    "😀", "😄", "😁", "😆", "😂", "🤣", "😊",
    "😇", "🙂", "😉", "😍", "🥰", "😘", "😋",
    "😜", "🤪", "😎", "🤩", "🥳", "😏", "🤔",
    "🤗", "🤫", "😮", "😢", "😭", "😤", "🤯",
    "👍", "👎", "👏", "🙌", "🤝", "🙏", "💪",
    "❤️", "🧡", "💛", "💚", "💙", "🔥", "🎉",
]

MAX_CHAT_BLOCKS = 5000          # Giới hạn số dòng giữ lại trong khung chat để tránh tốn RAM
PROGRESS_HIDE_DELAY_MS = 2000   # Ẩn thanh tiến độ sau khi lượt truyền cuối cùng kết thúc
INPUT_HISTORY_LIMIT = 100

STYLESHEET = """
QMainWindow, QWidget, QLabel, QPushButton, QLineEdit, QTextEdit, QComboBox, QProgressBar {
    font-family: "Plus Jakarta Sans", "Plus Jakarta Display", "Segoe UI", Arial, sans-serif;
}
QMainWindow, QWidget#centralWidget {
    background: #f4f6f9;
    color: #1b1a57;
}
QWidget#sidebar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f4f4f4);
    border-right: 1px solid #eaeef4;
    color: #1b1a57;
}
QWidget#profileCard {
    background: #f8faff;
    border: 1px solid #e6ecf5;
    border-radius: 14px;
}
QLabel {
    color: #1b1a57;
    background: transparent;
}
QLabel#myNameLabel {
    font-size: 15px;
    font-weight: 700;
    color: #1b1a57;
}
QLabel#myPortLabel {
    font-size: 11px;
    color: #4f5e7b;
}
QLabel#recentChatsTitle {
    font-size: 18px;
    font-weight: 700;
    color: #1b1a57;
}
QLineEdit#searchInput {
    background: #f5f7fb;
    color: #1b1a57;
    border: 1px solid #e2e8f2;
    border-radius: 16px;
    padding: 6px 12px;
    font-size: 12px;
}
QLineEdit#searchInput:focus {
    background: #ffffff;
    border: 1px solid #2f80ed;
}
QLabel#filterPillActive {
    background: #2f80ed;
    color: #ffffff;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 600;
}
QLabel#sectionLabel {
    background: #ffffff;
    color: #4f5e7b;
    border: 1px solid #e6ecf5;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 600;
}
QLabel#hintLabel {
    color: #4f5e7b;
    font-size: 11px;
    padding: 4px 2px;
}
QListWidget#peerList {
    border: none;
    background: transparent;
    outline: 0;
    color: #1b1a57;
}
QListWidget#peerList::item {
    border-radius: 10px;
    margin: 2px 4px;
    color: #1b1a57;
}
QListWidget#peerList::item:hover {
    background: #f2f7fe;
}
QListWidget#peerList::item:selected {
    background: #eaf2fd;
    color: #1b1a57;
}
QLabel#unreadBadge {
    background: #2f80ed;
    color: #ffffff;
    border-radius: 10px;
    padding: 2px 7px;
    font-size: 11px;
    font-weight: 700;
    min-width: 10px;
}
QWidget#rightPanel {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f4f4f4);
}
QWidget#chatHeaderBar {
    background: #ffffff;
    border-bottom: 1px solid #ededed;
}
QLabel#chatHeaderLabel {
    font-size: 17px;
    font-weight: 700;
    color: #1b1a57;
}
QLabel#chatSubLabel {
    font-size: 12px;
    color: #4f5e7b;
}
QScrollArea#chatScrollArea {
    background: transparent;
    border: none;
}
QWidget#chatCanvas {
    background: transparent;
}
QFrame#bubbleSelf {
    background: #2f80ed;
    border: none;
    border-radius: 16px;
}
QFrame#bubblePeer {
    background: #f7f7f7;
    border: 1px solid #eceff4;
    border-radius: 16px;
}
QFrame#bubbleRecalled {
    background: #f8f9fc;
    border: 1px dashed #cbd3e1;
    border-radius: 16px;
}
QFrame#systemNoticeCard {
    background: #f3f6fb;
    border: 1px solid #e5ebf5;
    border-radius: 10px;
}
QFrame#errorNoticeCard {
    background: #fff2f2;
    border: 1px solid #fad2d2;
    border-radius: 10px;
}
QFrame#unreadSeparatorCard {
    background: #fff2f2;
    border: 1px solid #fad2d2;
    border-radius: 10px;
}
QPushButton#bubbleMenuBtn {
    background: transparent;
    color: #a1a1bc;
    border: none;
    border-radius: 12px;
    font-size: 14px;
    font-weight: 700;
    min-width: 24px;
    max-width: 24px;
    min-height: 24px;
    max-height: 24px;
    padding: 0px;
}
QPushButton#bubbleMenuBtn:hover {
    background: #eaf2fd;
    color: #2f80ed;
}
QWidget#channelBar {
    background: #ffffff;
    border-top: 1px solid #ededed;
}
QLabel#channelTagLabel {
    color: #2f80ed;
    font-size: 12px;
    font-weight: 600;
}
QWidget#inputBar {
    background: #ffffff;
    border-top: 1px solid #ededed;
}
QLineEdit#messageInput {
    background: #f7f8fa;
    color: #1b1a57;
    selection-background-color: #2f80ed;
    selection-color: #ffffff;
    border: 1px solid #e6ecf5;
    border-radius: 18px;
    padding: 8px 14px;
    font-size: 13px;
}
QLineEdit#messageInput:focus {
    background: #ffffff;
    border: 1px solid #2f80ed;
    color: #1b1a57;
}
QPushButton {
    background: #2f80ed;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background: #1f6fd8;
}
QPushButton:disabled {
    background: #d5dce6;
    color: #ffffff;
}
QPushButton#emojiButton, QPushButton#sendFileButton {
    background: transparent;
    color: #4f5e7b;
    border: 1px solid transparent;
    border-radius: 18px;
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    max-height: 36px;
    padding: 0px;
}
QPushButton#emojiButton:hover, QPushButton#sendFileButton:hover {
    background: #eaf2fd;
}
QPushButton#sendFileButton:disabled {
    background: transparent;
}
QPushButton#leaveButton {
    background: #fff3f3;
    color: #eb5757;
    border: 1px solid #fad2d2;
    border-radius: 10px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#leaveButton:hover {
    background: #eb5757;
    color: #ffffff;
}
QPushButton#leaveButton:disabled {
    background: #f4f6f9;
    color: #a1a1bc;
    border: 1px solid #eaeef4;
}
QProgressBar {
    border: 1px solid #d5e6fb;
    border-radius: 8px;
    background: #eaf2fd;
    color: #1b1a57;
    text-align: center;
    font-size: 11px;
    font-weight: 600;
    height: 18px;
}
QProgressBar::chunk {
    background: #2f80ed;
    border-radius: 7px;
}
QComboBox {
    padding: 4px 10px;
    border: 1px solid #dce3ee;
    border-radius: 8px;
    background: #ffffff;
    color: #1b1a57;
    font-size: 12px;
    font-weight: 600;
}
QComboBox:hover {
    border: 1px solid #2f80ed;
}
QComboBox QAbstractItemView {
    background: #ffffff;
    color: #1b1a57;
    selection-background-color: #eaf2fd;
    selection-color: #1b1a57;
}
QMenu {
    background: #ffffff;
    color: #1b1a57;
    border: 1px solid #dce3ee;
    border-radius: 10px;
    padding: 6px;
}
QMenu::item {
    padding: 6px 14px;
    border-radius: 6px;
    font-size: 12px;
}
QMenu::item:selected {
    background: #eaf2fd;
    color: #2f80ed;
}
QSplitter::handle {
    background: #eaeef4;
    width: 1px;
}
QToolTip {
    background: #ffffff;
    color: #1b1a57;
    border: 1px solid #dce3ee;
}
"""


def _asset_path(filename: str) -> str:
    return os.path.join(ASSETS_DIR, filename)


def _load_svg_pixmap(filename: str, width: int, height: int) -> QPixmap:
    """Render file SVG trong ui/assets/ ra QPixmap sắc nét ở đúng kích thước."""
    path = _asset_path(filename)
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.transparent)
    if os.path.exists(path):
        renderer = QSvgRenderer(path)
        if renderer.isValid():
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            renderer.render(painter, QRectF(0, 0, width, height))
            painter.end()
    return pixmap


def _build_avatar_pixmap(
    name: str,
    size: int = 44,
    status: Optional[str] = "online",
    avatar_index: Optional[int] = None,
    custom_image_path: Optional[str] = None,
) -> QPixmap:
    """
    Tạo Avatar tròn theo đúng thiết kế Figma (Frame 1:146 & 1:499):
    - Ưu tiên ảnh custom do người dùng chọn từ máy tính (`custom_image_path`),
      hoặc ảnh mẫu trong `ui/assets/avatar_*.png`.
    - Đè icon chấm trạng thái SVG (status_online.svg / status_away.svg / status_offline.svg) ở góc dưới phải.
    """
    canvas = QPixmap(size, size)
    canvas.fill(Qt.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)

    idx = (avatar_index if avatar_index is not None else sum(ord(c) for c in (name or "?"))) % len(AVATAR_FILES)
    avatar_path = custom_image_path if (custom_image_path and os.path.exists(custom_image_path)) else _asset_path(AVATAR_FILES[idx])

    circle_path = QPainterPath()
    circle_path.addEllipse(0, 0, size, size)
    painter.save()
    painter.setClipPath(circle_path)

    source = QPixmap(avatar_path) if os.path.exists(avatar_path) else QPixmap()
    if not source.isNull():
        scaled = source.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        sx = max(0, (scaled.width() - size) // 2)
        sy = max(0, (scaled.height() - size) // 2)
        painter.drawPixmap(0, 0, scaled, sx, sy, size, size)
    else:
        bg_color = QColor(AVATAR_FALLBACK_COLORS[idx % len(AVATAR_FALLBACK_COLORS)])
        painter.fillPath(circle_path, bg_color)
        painter.setPen(QColor("#ffffff"))
        font = QFont("Plus Jakarta Sans", max(10, size // 3))
        font.setBold(True)
        painter.setFont(font)
        initial = (name.strip()[:1] if name and name.strip() else "?").upper()
        painter.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, initial)
    painter.restore()

    if status is not None:
        svg_name = {
            "online": "status_online.svg",
            "away": "status_away.svg",
        }.get(status, "status_offline.svg")
        dot_size = max(12, size // 4)
        dot_pix = _load_svg_pixmap(svg_name, dot_size, dot_size)
        painter.drawPixmap(size - dot_size, size - dot_size, dot_pix)

    painter.end()
    return canvas


class ClickableAvatarLabel(QLabel):
    """Nhãn Avatar cho phép click chuột trái/phải để mở menu Đổi Avatar."""

    clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() in (Qt.LeftButton, Qt.RightButton):
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class ChatBubbleWidget(QFrame):
    """
    Widget Bong bóng Tin nhắn bo góc tròn thật sự (border-radius: 16px):
    - Hỗ trợ click chuột phải hoặc bấm nút '⋯' bên cạnh bong bóng để:
      + 'Xóa ở phía bạn' (Delete for me)
      + 'Thu hồi tin nhắn' (Unsend for everyone - như Messenger, dành cho tin nhắn của chính mình)
    """

    def __init__(
        self,
        message: ChatMessage,
        is_self: bool,
        on_delete_for_me: Callable[[ChatMessage], None],
        on_recall_message: Callable[[ChatMessage], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.message = message
        self.is_self = is_self
        self._on_delete_for_me = on_delete_for_me
        self._on_recall_message = on_recall_message

        self.outer_layout = QHBoxLayout(self)
        self.outer_layout.setContentsMargins(4, 3, 4, 3)
        self.outer_layout.setSpacing(6)

        self.bubble_frame = QFrame(self)
        self.bubble_frame.setMaximumWidth(480)
        self.bubble_layout = QVBoxLayout(self.bubble_frame)
        self.bubble_layout.setContentsMargins(14, 10, 14, 8)
        self.bubble_layout.setSpacing(4)

        self.content_label = QLabel(self.bubble_frame)
        self.content_label.setWordWrap(True)
        self.content_label.setTextFormat(Qt.RichText)
        self.content_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.bubble_layout.addWidget(self.content_label)

        self.time_label = QLabel(self.bubble_frame)
        self.time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.bubble_layout.addWidget(self.time_label)

        self.menu_btn = QPushButton("\u22ef", self)
        self.menu_btn.setObjectName("bubbleMenuBtn")
        self.menu_btn.setCursor(Qt.PointingHandCursor)
        self.menu_btn.setToolTip("Tùy chọn tin nhắn (Xóa / Thu hồi)")
        self.menu_btn.clicked.connect(self._show_actions_menu)

        if is_self:
            self.outer_layout.addStretch(1)
            self.outer_layout.addWidget(self.menu_btn, 0, Qt.AlignVCenter)
            self.outer_layout.addWidget(self.bubble_frame, 0)
        else:
            self.outer_layout.addWidget(self.bubble_frame, 0)
            self.outer_layout.addWidget(self.menu_btn, 0, Qt.AlignVCenter)
            self.outer_layout.addStretch(1)

        self.refresh_appearance()

    def refresh_appearance(self) -> None:
        """Cập nhật giao diện bong bóng (bình thường hoặc đã bị thu hồi như Messenger)."""
        timestamp = time.strftime("%H:%M:%S", time.localtime(self.message.timestamp))
        sender_escaped = html.escape(self.message.sender_name)

        if self.message.is_recalled:
            self.bubble_frame.setObjectName("bubbleRecalled")
            recalled_text = (
                "Bạn đã thu hồi một tin nhắn"
                if self.is_self
                else f"{sender_escaped} đã thu hồi một tin nhắn"
            )
            self.content_label.setText(
                f'<span style="color:#8c97ac; font-style:italic; font-size:13px;">'
                f"\U0001f6ab {recalled_text}</span>"
            )
            self.time_label.setText(timestamp)
            self.time_label.setStyleSheet("color: #a1a1bc; font-size: 10px;")
        elif self.is_self:
            self.bubble_frame.setObjectName("bubbleSelf")
            escaped_body = MainWindow._escape_multiline(self.message.content)
            self.content_label.setText(
                f'<b style="color:#d5e6fb; font-size:11px;">[{sender_escaped}]</b> '
                f'<span style="color:#ffffff; font-size:13px; line-height:18px;">{escaped_body}</span>'
            )
            self.time_label.setText(timestamp)
            self.time_label.setStyleSheet("color: #d5e6fb; font-size: 10px;")
        else:
            self.bubble_frame.setObjectName("bubblePeer")
            escaped_body = MainWindow._escape_multiline(self.message.content)
            self.content_label.setText(
                f'<b style="color:{PEER_COLOR}; font-size:12px;">[{sender_escaped}]</b> '
                f'<span style="color:{TEXT_COLOR}; font-size:13px; line-height:18px;">{escaped_body}</span>'
            )
            self.time_label.setText(timestamp)
            self.time_label.setStyleSheet(f"color: {PLACEHOLDER_COLOR}; font-size: 10px;")

        self.bubble_frame.style().unpolish(self.bubble_frame)
        self.bubble_frame.style().polish(self.bubble_frame)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # noqa: N802
        self._open_menu_at(event.globalPos())
        event.accept()

    @Slot()
    def _show_actions_menu(self) -> None:
        pos = self.menu_btn.mapToGlobal(QPoint(0, self.menu_btn.height()))
        self._open_menu_at(pos)

    def _open_menu_at(self, global_pos: QPoint) -> None:
        menu = QMenu(self)
        if self.is_self and not self.message.is_recalled:
            recall_action = QAction("\u21a9\ufe0f  Thu hồi tin nhắn (với mọi người)", menu)
            recall_action.triggered.connect(lambda: self._on_recall_message(self.message))
            menu.addAction(recall_action)

        delete_action = QAction("\U0001f5d1\ufe0f  Xóa ở phía bạn", menu)
        delete_action.triggered.connect(lambda: self._on_delete_for_me(self.message))
        menu.addAction(delete_action)
        menu.exec(global_pos)


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
    """
    Một dòng người dùng trên Sidebar theo thiết kế Figma (Frame 1:146, cao 64px):
    - Avatar tròn 44x44px kèm chấm trạng thái SVG (online xanh lá, away vàng).
    - Cột giữa: Số thứ tự + Tên (#1B1A57 Medium 13px) và icon check + Địa chỉ IP:Port (#4F5E7B 12px).
    - Cột phải: Trạng thái/nhãn "Active" và badge số tin chưa đọc (#2F80ED pill).
    """

    def __init__(self, index: int, peer: PeerInfo, unread: int, is_active: bool) -> None:
        super().__init__()
        self.setAttribute(Qt.WA_TransparentForMouseEvents)  # để click đi xuống QListWidget

        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(12)

        # 1. Avatar + Status Dot SVG
        avatar_label = QLabel()
        avatar_label.setFixedSize(44, 44)
        avatar_label.setPixmap(_build_avatar_pixmap(peer.name, size=44, status=peer.status, avatar_index=index - 1))
        avatar_label.setToolTip(peer.status)
        outer.addWidget(avatar_label, 0, Qt.AlignVCenter)

        # 2. Tên & Địa chỉ IP:Port
        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(3)

        name_label = QLabel(f"{index}. {peer.name}")
        name_label.setTextFormat(Qt.PlainText)
        name_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        name_label.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 13px;")
        name_font = name_label.font()
        name_font.setBold(True if (is_active or unread > 0) else False)
        name_font.setWeight(QFont.Bold if (is_active or unread > 0) else QFont.Medium)
        name_label.setFont(name_font)

        sub_row = QHBoxLayout()
        sub_row.setContentsMargins(0, 0, 0, 0)
        sub_row.setSpacing(4)

        check_icon = QLabel()
        check_icon.setFixedSize(14, 14)
        check_icon.setPixmap(_load_svg_pixmap("icon_check.svg", 14, 14))
        sub_row.addWidget(check_icon, 0, Qt.AlignVCenter)

        status_text = f" \u00b7 {peer.status}" if peer.status != "online" else ""
        addr_label = QLabel(f"{peer.ip}:{peer.tcp_port}{status_text}")
        addr_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        addr_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        sub_row.addWidget(addr_label, 1)

        text_box.addWidget(name_label)
        text_box.addLayout(sub_row)
        outer.addLayout(text_box, 1)

        # 3. Cột phải: Thời gian/Trạng thái + Unread Badge (#2F80ED)
        right_box = QVBoxLayout()
        right_box.setContentsMargins(0, 0, 0, 0)
        right_box.setSpacing(4)
        right_box.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        meta_label = QLabel("Active" if is_active else peer.status.capitalize())
        meta_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        meta_color = PRIMARY_BLUE if is_active else PLACEHOLDER_COLOR
        meta_label.setStyleSheet(f"color: {meta_color}; font-size: 11px; font-weight: 600;")
        right_box.addWidget(meta_label, 0, Qt.AlignRight)

        self.badge = QLabel("99+" if unread > 99 else str(unread))
        self.badge.setObjectName("unreadBadge")
        self.badge.setAlignment(Qt.AlignCenter)
        self.badge.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.badge.setVisible(unread > 0)
        right_box.addWidget(self.badge, 0, Qt.AlignRight)

        outer.addLayout(right_box, 0)


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
        self.search_input: QLineEdit
        self.status_combo: QComboBox
        self.chat_header_label: QLabel
        self.chat_sub_label: QLabel
        self.chat_display: QTextEdit
        self.chat_scroll_area: QScrollArea
        self.chat_canvas: QWidget
        self.chat_bubbles_layout: QVBoxLayout
        self.file_progress_bar: QProgressBar
        self.message_input: HistoryLineEdit
        self.emoji_btn: QPushButton
        self.send_btn: QPushButton
        self.send_file_btn: QPushButton
        self.leave_btn: QPushButton
        self.online_count_label: QLabel
        self.my_name_label: QLabel
        self.my_avatar_label: ClickableAvatarLabel
        self.chat_avatar_label: QLabel
        self.channel_bar: QWidget
        self.channel_tag_label: QLabel

        # Trạng thái riêng của giao diện (chỉ truy cập từ Main Thread)
        self._active_peer_id: Optional[str] = None
        self._pending_sidebar_peer_id: Optional[str] = None
        self._peer_names: Dict[str, str] = {}              # cache peer_id -> tên (kể cả khi peer đã offline)
        self._rendered_message_ids: Set[int] = set()       # chống hiển thị trùng 1 tin nhắn
        self._bubble_widgets: Dict[int, ChatBubbleWidget] = {}  # id(message) -> widget bong bóng
        self._deleted_for_me_ids: Set[int] = set()         # id(message) đã bấm "Xóa ở phía bạn"
        self._transfers: Dict[Tuple[str, str], int] = {}   # (peer_id, filename) -> % đang truyền
        self._finished_transfers: Set[Tuple[str, str]] = set()
        self._syncing_status = False
        self._search_filter_text: str = ""
        self._my_avatar_index: int = 1
        self._my_custom_avatar_path: Optional[str] = None

        self._progress_hide_timer = QTimer(self)
        self._progress_hide_timer.setSingleShot(True)
        self._progress_hide_timer.timeout.connect(self._hide_progress_if_idle)

        self._setup_ui()
        self._connect_signals()
        self._apply_active_peer(None)
        self.on_peer_list_updated()
        self._show_welcome()

    # ------------------------------------------------------------------
    # Xây dựng giao diện theo Figma "Messaging App UI"
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        my_name, my_port, my_status = self.shared_state.get_my_info()
        self.resize(1060, 680)
        self.setMinimumSize(760, 480)
        self._apply_light_palette()
        self.setStyleSheet(STYLESHEET)

        base_font = QFont("Plus Jakarta Sans", 10)
        if not base_font.exactMatch():
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

        # ==================================================================
        # CỘT TRÁI: SIDEBAR ("Home / Recent Chats" - Figma Frame 1:146)
        # ==================================================================
        left_panel = QWidget()
        left_panel.setObjectName("sidebar")
        left_panel.setMinimumWidth(290)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 16, 12)
        left_layout.setSpacing(10)

        # 1. Thẻ thông tin cá nhân (Click vào Avatar để đổi Avatar!)
        profile_card = QFrame()
        profile_card.setObjectName("profileCard")
        profile_layout = QHBoxLayout(profile_card)
        profile_layout.setContentsMargins(10, 10, 10, 10)
        profile_layout.setSpacing(10)

        self.my_avatar_label = ClickableAvatarLabel()
        self.my_avatar_label.setFixedSize(44, 44)
        self.my_avatar_label.setToolTip("Click để đổi Avatar của bạn (chọn ảnh từ máy hoặc mẫu Figma)")
        self._refresh_my_avatar()
        profile_layout.addWidget(self.my_avatar_label, 0, Qt.AlignVCenter)

        my_info_box = QVBoxLayout()
        my_info_box.setContentsMargins(0, 0, 0, 0)
        my_info_box.setSpacing(2)
        self.my_name_label = QLabel(my_name)
        self.my_name_label.setObjectName("myNameLabel")
        port_label = QLabel(f"TCP:{my_port} \u2022 Đổi avatar")
        port_label.setObjectName("myPortLabel")
        my_info_box.addWidget(self.my_name_label)
        my_info_box.addWidget(port_label)
        profile_layout.addLayout(my_info_box, 1)

        self.status_combo = QComboBox()
        self.status_combo.addItem("\u25cf online", "online")
        self.status_combo.addItem("\u25cf away", "away")
        self.status_combo.setToolTip("Your presence status (same as /status <online|away>)")
        self._set_combo_status(my_status)
        profile_layout.addWidget(self.status_combo, 0, Qt.AlignVCenter)
        left_layout.addWidget(profile_card)

        # 2. Tiêu đề "Recent Chats" (Đã bỏ icon kính lúp tĩnh theo yêu cầu)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(2, 2, 2, 0)
        recent_title = QLabel("Recent Chats")
        recent_title.setObjectName("recentChatsTitle")
        title_row.addWidget(recent_title, 1)
        left_layout.addLayout(title_row)

        # 3. Ô tìm kiếm bạn bè bo tròn (có icon kính lúp bên trong)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("Tìm kiếm bạn bè theo tên hoặc IP...")
        self.search_input.setClearButtonEnabled(True)
        search_action = QAction(QIcon(_load_svg_pixmap("icon_search.svg", 16, 16)), "", self.search_input)
        self.search_input.addAction(search_action, QLineEdit.LeadingPosition)
        left_layout.addWidget(self.search_input)

        # 4. Hàng Filter Pills ("All chats" #2F80ED + "ONLINE USERS (N)")
        pills_row = QHBoxLayout()
        pills_row.setContentsMargins(2, 0, 2, 2)
        pills_row.setSpacing(8)

        all_chats_pill = QLabel("All chats")
        all_chats_pill.setObjectName("filterPillActive")
        pills_row.addWidget(all_chats_pill, 0)

        self.online_count_label = QLabel("ONLINE USERS (0)")
        self.online_count_label.setObjectName("sectionLabel")
        pills_row.addWidget(self.online_count_label, 0)
        pills_row.addStretch(1)
        left_layout.addLayout(pills_row)

        # 5. Danh sách Online Peers
        self.peer_list_widget = QListWidget()
        self.peer_list_widget.setObjectName("peerList")
        self.peer_list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.peer_list_widget.setSpacing(2)
        self.peer_list_widget.setToolTip("Click a user to open a chat (same as /chat <number>)")
        left_layout.addWidget(self.peer_list_widget, 1)

        hint = QLabel("Click a user to chat \u2022 /help for commands")
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        left_layout.addWidget(hint)
        splitter.addWidget(left_panel)

        # ==================================================================
        # CỘT PHẢI: KHUNG CHAT CHÍNH ("Group Chat" - Figma Frame 1:499)
        # ==================================================================
        right_panel = QWidget()
        right_panel.setObjectName("rightPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # 1. Thanh Header Khung Chat (Đã bỏ icon máy quay Video theo yêu cầu)
        header_bar = QWidget()
        header_bar.setObjectName("chatHeaderBar")
        header_bar.setFixedHeight(74)
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(18, 12, 18, 12)
        header_layout.setSpacing(12)

        self.chat_avatar_label = QLabel()
        self.chat_avatar_label.setFixedSize(46, 46)
        self.chat_avatar_label.setPixmap(_build_avatar_pixmap("LAN", size=46, status="online", avatar_index=1))
        header_layout.addWidget(self.chat_avatar_label, 0, Qt.AlignVCenter)

        header_text = QVBoxLayout()
        header_text.setContentsMargins(0, 0, 0, 0)
        header_text.setSpacing(2)
        self.chat_header_label = QLabel()
        self.chat_header_label.setObjectName("chatHeaderLabel")
        self.chat_sub_label = QLabel()
        self.chat_sub_label.setObjectName("chatSubLabel")
        header_text.addWidget(self.chat_header_label)
        header_text.addWidget(self.chat_sub_label)
        header_layout.addLayout(header_text, 1)

        self.leave_btn = QPushButton(" Leave (/leave)")
        self.leave_btn.setObjectName("leaveButton")
        self.leave_btn.setIcon(QIcon(_load_svg_pixmap("icon_leave.svg", 16, 16)))
        self.leave_btn.setIconSize(QSize(16, 16))
        self.leave_btn.setToolTip("Close the current chat")
        header_layout.addWidget(self.leave_btn, 0, Qt.AlignVCenter)

        right_layout.addWidget(header_bar)

        # 2. Vùng hiển thị lịch sử tin nhắn bo góc tròn thật sự (QScrollArea chứa ChatBubbleWidget)
        self.chat_scroll_area = QScrollArea()
        self.chat_scroll_area.setObjectName("chatScrollArea")
        self.chat_scroll_area.setWidgetResizable(True)
        self.chat_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_scroll_area.setFocusPolicy(Qt.NoFocus)

        self.chat_canvas = QWidget()
        self.chat_canvas.setObjectName("chatCanvas")
        self.chat_bubbles_layout = QVBoxLayout(self.chat_canvas)
        self.chat_bubbles_layout.setContentsMargins(16, 14, 16, 14)
        self.chat_bubbles_layout.setSpacing(8)
        self.chat_bubbles_layout.addStretch(1)
        self.chat_scroll_area.setWidget(self.chat_canvas)
        right_layout.addWidget(self.chat_scroll_area, 1)

        # Giữ `self.chat_display` (QTextEdit ẩn) đồng bộ 100% dữ liệu văn bản cho bộ SelfTest
        self.chat_display = QTextEdit(right_panel)
        self.chat_display.setObjectName("chatDisplay")
        self.chat_display.setReadOnly(True)
        self.chat_display.document().setMaximumBlockCount(MAX_CHAT_BLOCKS)
        self.chat_display.setVisible(False)

        # 3. Thanh Tiến độ truyền File (Đã bỏ icon mũi tên & 3 chấm thừa)
        self.channel_bar = QWidget()
        self.channel_bar.setObjectName("channelBar")
        channel_layout = QHBoxLayout(self.channel_bar)
        channel_layout.setContentsMargins(16, 6, 16, 6)
        channel_layout.setSpacing(10)

        self.channel_tag_label = QLabel("# General")
        self.channel_tag_label.setObjectName("channelTagLabel")
        channel_layout.addWidget(self.channel_tag_label, 0, Qt.AlignVCenter)

        self.file_progress_bar = QProgressBar()
        self.file_progress_bar.setRange(0, 100)
        self.file_progress_bar.setValue(0)
        self.file_progress_bar.setVisible(False)
        channel_layout.addWidget(self.file_progress_bar, 1, Qt.AlignVCenter)

        right_layout.addWidget(self.channel_bar)

        # 4. Thanh nhập tin nhắn (Nút Emoji mở bảng chọn + Ô nhập nhấn Enter để gửi + Nút đính kèm file)
        # Đã bỏ nút tròn Micro ở góc dưới phải theo yêu cầu.
        input_bar = QWidget()
        input_bar.setObjectName("inputBar")
        input_layout = QHBoxLayout(input_bar)
        input_layout.setContentsMargins(16, 10, 16, 12)
        input_layout.setSpacing(10)

        self.emoji_btn = QPushButton("")
        self.emoji_btn.setObjectName("emojiButton")
        self.emoji_btn.setCursor(Qt.PointingHandCursor)
        self.emoji_btn.setIcon(QIcon(_load_svg_pixmap("icon_emoji.svg", 22, 22)))
        self.emoji_btn.setIconSize(QSize(22, 22))
        self.emoji_btn.setToolTip("Chọn biểu tượng cảm xúc (Emoji)")
        input_layout.addWidget(self.emoji_btn, 0, Qt.AlignVCenter)

        self.message_input = HistoryLineEdit()
        self.message_input.setObjectName("messageInput")
        self.message_input.setPlaceholderText(
            "Write a message and press Enter... (or /list, /chat, /send, /status, /leave, /help, /quit)"
        )
        self.message_input.setClearButtonEnabled(True)
        input_layout.addWidget(self.message_input, 1)

        self.send_file_btn = QPushButton("")
        self.send_file_btn.setObjectName("sendFileButton")
        self.send_file_btn.setCursor(Qt.PointingHandCursor)
        self.send_file_btn.setIcon(QIcon(_load_svg_pixmap("icon_attachment.svg", 22, 22)))
        self.send_file_btn.setIconSize(QSize(22, 22))
        self.send_file_btn.setToolTip("Pick a file and send it to the current chat partner (/send <file>)")
        input_layout.addWidget(self.send_file_btn, 0, Qt.AlignVCenter)

        # Giữ thuộc tính `self.send_btn` ẩn để tương thích nếu script kiểm thử truy cập `window.send_btn`
        self.send_btn = QPushButton("Send", input_bar)
        self.send_btn.setVisible(False)

        right_layout.addWidget(input_bar)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([330, 730])

        self.message_input.ensurePolished()
        input_palette = self.message_input.palette()
        input_palette.setColor(QPalette.Base, QColor("#f7f8fa"))
        input_palette.setColor(QPalette.Text, QColor(TEXT_COLOR))
        input_palette.setColor(QPalette.PlaceholderText, QColor(PLACEHOLDER_COLOR))
        self.message_input.setPalette(input_palette)
        self.message_input.setFocus()

    def _connect_signals(self) -> None:
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
        self.emoji_btn.clicked.connect(self._on_emoji_clicked)
        self.my_avatar_label.clicked.connect(self._on_change_avatar_clicked)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.leave_btn.clicked.connect(self._on_leave_clicked)
        self.peer_list_widget.itemClicked.connect(self._on_peer_item_activated)
        self.peer_list_widget.itemActivated.connect(self._on_peer_item_activated)
        self.status_combo.currentIndexChanged.connect(self._on_status_combo_changed)

    # ------------------------------------------------------------------
    # Tính năng mới: Đổi Avatar, Bảng chọn Emoji, Tìm kiếm, Xóa & Thu hồi
    # ------------------------------------------------------------------

    def _refresh_my_avatar(self) -> None:
        my_name, _, my_status = self.shared_state.get_my_info()
        pix = _build_avatar_pixmap(
            my_name,
            size=44,
            status=my_status,
            avatar_index=self._my_avatar_index,
            custom_image_path=self._my_custom_avatar_path,
        )
        self.my_avatar_label.setPixmap(pix)

    @Slot()
    def _on_change_avatar_clicked(self) -> None:
        """Mở menu chọn ảnh từ máy tính hoặc chọn nhanh 1 trong 5 mẫu Avatar Figma."""
        menu = QMenu(self)
        pick_file_action = QAction("\U0001f4c1  Chọn ảnh bất kỳ từ máy tính...", menu)
        pick_file_action.triggered.connect(self._pick_custom_avatar_file)
        menu.addAction(pick_file_action)
        menu.addSeparator()

        for idx, filename in enumerate(AVATAR_FILES):
            icon_pix = _build_avatar_pixmap(f"A{idx+1}", size=28, status=None, avatar_index=idx)
            preset_action = QAction(QIcon(icon_pix), f"Mẫu Avatar Figma #{idx + 1}", menu)
            preset_action.triggered.connect(lambda _checked=False, i=idx: self._set_preset_avatar(i))
            menu.addAction(preset_action)

        pos = self.my_avatar_label.mapToGlobal(QPoint(0, self.my_avatar_label.height() + 4))
        menu.exec(pos)

    def _pick_custom_avatar_file(self) -> None:
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn ảnh làm Avatar",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.webp);;All Files (*)",
        )
        if filepath and os.path.isfile(filepath):
            self._my_custom_avatar_path = filepath
            self._refresh_my_avatar()
            self.on_system_notification(f"[*] Đã cập nhật Avatar từ file: {os.path.basename(filepath)}")
        self.message_input.setFocus()

    def _set_preset_avatar(self, index: int) -> None:
        self._my_custom_avatar_path = None
        self._my_avatar_index = index
        self._refresh_my_avatar()
        self.on_system_notification(f"[*] Đã đổi sang Mẫu Avatar Figma #{index + 1}.")
        self.message_input.setFocus()

    @Slot()
    def _on_emoji_clicked(self) -> None:
        """Hiển thị Bảng chọn Emoji (Popup Grid 7 cột) để chèn nhanh vào ô nhập tin nhắn."""
        menu = QMenu(self)
        container = QWidget(menu)
        grid = QGridLayout(container)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(4)

        cols = 7
        for idx, emoji_char in enumerate(EMOJI_LIST):
            btn = QPushButton(emoji_char, container)
            btn.setFixedSize(34, 34)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background: transparent; border: none; border-radius: 6px; font-size: 18px; padding: 0; }"
                "QPushButton:hover { background: #eaf2fd; }"
            )
            btn.clicked.connect(lambda _checked=False, e=emoji_char, m=menu: self._insert_emoji(e, m))
            grid.addWidget(btn, idx // cols, idx % cols)

        widget_action = QWidgetAction(menu)
        widget_action.setDefaultWidget(container)
        menu.addAction(widget_action)

        pos = self.emoji_btn.mapToGlobal(QPoint(0, -container.sizeHint().height() - 12))
        menu.exec(pos)

    def _insert_emoji(self, emoji_char: str, menu: QMenu) -> None:
        menu.close()
        self.message_input.insert(emoji_char)
        self.message_input.setFocus()

    @Slot(str)
    def _on_search_text_changed(self, text: str) -> None:
        """Lọc danh sách bạn bè trên Sidebar theo tên, IP:Port hoặc trạng thái."""
        self._search_filter_text = (text or "").strip().lower()
        self.on_peer_list_updated()

    def _delete_message_for_me(self, message: ChatMessage) -> None:
        """Xóa tin nhắn ở phía mình (Delete for you)."""
        msg_id = id(message)
        self._deleted_for_me_ids.add(msg_id)
        if self._active_peer_id:
            history_list = self.shared_state.chat_histories.get(self._active_peer_id, [])
            if message in history_list:
                history_list.remove(message)

        widget = self._bubble_widgets.pop(msg_id, None)
        if widget is not None:
            self.chat_bubbles_layout.removeWidget(widget)
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        self._rebuild_plain_text_mirror()
        self.message_input.setFocus()

    def _recall_message_for_everyone(self, message: ChatMessage) -> None:
        """
        Thu hồi tin nhắn ở cả 2 phía (như Messenger):
        - Đổi bong bóng ở máy mình sang '🚫 Bạn đã thu hồi một tin nhắn' và thông báo trên khung chat.
        - Gửi khung điều khiển `__LANCHAT_RECALL__|<nội dung gốc>` qua TCP sang máy đối phương.
        """
        if message.is_recalled or message.sender_id != SELF_SENDER_ID:
            return
        original_content = message.content
        message.is_recalled = True
        message.content = "Bạn đã thu hồi một tin nhắn"

        widget = self._bubble_widgets.get(id(message))
        if widget is not None:
            widget.refresh_appearance()

        if self._active_peer_id:
            try:
                self.command_parser.tcp_manager.send_text_message(
                    self._active_peer_id,
                    f"{RECALL_PREFIX}{original_content}",
                )
            except Exception:
                pass

        self._rebuild_plain_text_mirror()
        self.on_system_notification("[*] Bạn đã thu hồi một tin nhắn.")
        self.message_input.setFocus()

    # ------------------------------------------------------------------
    # Hành động của người dùng -> CommandParser
    # ------------------------------------------------------------------

    @Slot()
    def _on_submit_input(self) -> None:
        text = self.message_input.text()
        if not text.strip():
            return
        self.message_input.remember(text.strip())
        self.message_input.clear()
        self.command_parser.handle_user_input(text)
        self.message_input.setFocus()

    @Slot(QListWidgetItem)
    def _on_peer_item_activated(self, item: QListWidgetItem) -> None:
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
                self.on_peer_list_updated()
        self.message_input.setFocus()

    @Slot()
    def _on_send_file_clicked(self) -> None:
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
        peers = self.shared_state.get_online_peers()
        scroll_value = self.peer_list_widget.verticalScrollBar().value()

        self.peer_list_widget.setUpdatesEnabled(False)
        self.peer_list_widget.clear()
        for index, peer in enumerate(peers, start=1):
            self._peer_names[peer.peer_id] = peer.name
            if self._search_filter_text:
                haystack = f"{index} {peer.name} {peer.ip}:{peer.tcp_port} {peer.status}".lower()
                if self._search_filter_text not in haystack:
                    continue

            is_active = peer.peer_id == self._active_peer_id
            unread = 0 if is_active else self.shared_state.get_unread_count(peer.peer_id)

            item = QListWidgetItem()
            item.setData(Qt.UserRole, peer.peer_id)
            item.setToolTip(
                f"{peer.name}\n{peer.ip}:{peer.tcp_port}\nStatus: {peer.status}"
                + (f"\nUnread: {unread}" if unread else "")
            )
            row_widget = PeerItemWidget(index, peer, unread, is_active)
            item.setSizeHint(QSize(0, max(62, row_widget.sizeHint().height())))
            self.peer_list_widget.addItem(item)
            self.peer_list_widget.setItemWidget(item, row_widget)
            item.setSelected(is_active)
        self.peer_list_widget.setUpdatesEnabled(True)
        self.peer_list_widget.verticalScrollBar().setValue(scroll_value)

        self.online_count_label.setText(f"ONLINE USERS ({len(peers)})")
        self._refresh_chat_header(peers)

    @Slot(str)
    def on_system_notification(self, text: str) -> None:
        if not text:
            return
        is_error = text.lstrip().startswith("[!]")
        color = ERROR_COLOR if is_error else SYSTEM_COLOR
        card_name = "errorNoticeCard" if is_error else "systemNoticeCard"

        card = QFrame(self.chat_canvas)
        card.setObjectName(card_name)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(12, 7, 12, 7)

        label = QLabel(card)
        label.setWordWrap(True)
        label.setTextFormat(Qt.RichText)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setText(
            f"<span style=\"color:{color}; font-family:Consolas,'Courier New',monospace; font-size:12px;\">"
            f"{self._escape_multiline(text)}</span>"
        )
        card_layout.addWidget(label)
        self._add_chat_widget(card)

        self._append_html(
            f'<span style="color:{color};">{self._escape_multiline(text)}</span>',
            monospace=True,
        )

    @Slot(str, object)
    def on_chat_message_received(self, peer_id: str, message: object) -> None:
        if isinstance(message, ChatMessage) and message.content.startswith(RECALL_PREFIX):
            # Hỗ trợ cả khi chạy qua MockTCPManager / deliver_message trong tests
            target_text = message.content[len(RECALL_PREFIX):]
            history_list = self.shared_state.chat_histories.get(peer_id, [])
            if message in history_list:
                history_list.remove(message)
            sender_name = self._peer_display_name(peer_id)
            for candidate in reversed(history_list):
                if not candidate.is_recalled and candidate.content == target_text:
                    candidate.is_recalled = True
                    candidate.content = f"{sender_name} đã thu hồi một tin nhắn"
                    widget = self._bubble_widgets.get(id(candidate))
                    if widget is not None:
                        widget.refresh_appearance()
                    break
            self._rebuild_plain_text_mirror()
            self.on_system_notification(f"[*] {sender_name} đã thu hồi một tin nhắn.")
            return

        if peer_id == self._active_peer_id:
            if isinstance(message, ChatMessage) and id(message) in self._rendered_message_ids:
                # Nếu là tin nhắn vừa được đánh dấu thu hồi từ luồng TCP, cập nhật lại bong bóng hiện có
                if message.is_recalled and id(message) in self._bubble_widgets:
                    self._bubble_widgets[id(message)].refresh_appearance()
                    self._rebuild_plain_text_mirror()
                return
            self._rendered_message_ids.add(id(message))
            if isinstance(message, ChatMessage) and id(message) not in self._deleted_for_me_ids:
                self._add_message_bubble(message)
            self._append_html(self._format_message(message))
            return

        self.on_peer_list_updated()
        if not self.isActiveWindow():
            QApplication.alert(self)

    @Slot(str, str, int)
    def on_file_progress_updated(self, peer_id: str, filename: str, percentage: int) -> None:
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
        self._clear_chat_widgets()
        self.chat_display.clear()
        self._rendered_message_ids.clear()
        self._apply_active_peer(peer)

        if peer is None:
            self._show_welcome()
            return

        messages = [m for m in list(history or []) if id(m) not in self._deleted_for_me_ids]
        first_unread = len(messages) - unread if 0 < unread <= len(messages) else None
        if not messages:
            self.on_system_notification(f"[*] This is the beginning of your chat with {peer.name}.")
        for index, message in enumerate(messages):
            if index == first_unread:
                self._add_unread_separator_widget(unread)
                self._append_html(
                    f'<span style="color:{ERROR_COLOR};">\u2500\u2500\u2500\u2500  {unread} unread  \u2500\u2500\u2500\u2500</span>'
                )
            self._rendered_message_ids.add(id(message))
            if isinstance(message, ChatMessage):
                self._add_message_bubble(message)
            self._append_html(self._format_message(message))

    @Slot(str)
    def on_my_status_changed(self, status: str) -> None:
        self._set_combo_status(status)
        self._refresh_my_avatar()
        self._update_window_title()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._progress_hide_timer.stop()
        self.command_parser.shutdown()
        event.accept()

    # ------------------------------------------------------------------
    # Quản lý danh sách Widget Bong bóng Tin nhắn bo góc tròn
    # ------------------------------------------------------------------

    def _clear_chat_widgets(self) -> None:
        self._bubble_widgets.clear()
        while self.chat_bubbles_layout.count() > 1:
            item = self.chat_bubbles_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

    def _add_chat_widget(self, widget: QWidget) -> None:
        scrollbar = self.chat_scroll_area.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum() - 8
        insert_idx = max(0, self.chat_bubbles_layout.count() - 1)
        self.chat_bubbles_layout.insertWidget(insert_idx, widget)
        if at_bottom:
            QTimer.singleShot(0, lambda: scrollbar.setValue(scrollbar.maximum()))

    def _add_message_bubble(self, message: ChatMessage) -> None:
        if message.is_system:
            self.on_system_notification(message.content)
            return
        is_self = message.sender_id == SELF_SENDER_ID
        bubble = ChatBubbleWidget(
            message=message,
            is_self=is_self,
            on_delete_for_me=self._delete_message_for_me,
            on_recall_message=self._recall_message_for_everyone,
            parent=self.chat_canvas,
        )
        self._bubble_widgets[id(message)] = bubble
        self._add_chat_widget(bubble)

    def _add_unread_separator_widget(self, unread: int) -> None:
        card = QFrame(self.chat_canvas)
        card.setObjectName("unreadSeparatorCard")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 5, 12, 5)
        lbl = QLabel(f"\u2500\u2500\u2500\u2500  {unread} unread  \u2500\u2500\u2500\u2500", card)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"color: {ERROR_COLOR}; font-weight: 700; font-size: 11px;")
        layout.addWidget(lbl)
        self._add_chat_widget(card)

    def _rebuild_plain_text_mirror(self) -> None:
        """Đồng bộ lại `self.chat_display` khi có tin nhắn bị xóa hoặc thu hồi."""
        if self._active_peer_id is None:
            return
        self.chat_display.clear()
        for msg in self.shared_state.chat_histories.get(self._active_peer_id, []):
            if id(msg) not in self._deleted_for_me_ids:
                self._append_html(self._format_message(msg))

    # ------------------------------------------------------------------
    # Tiện ích hiển thị
    # ------------------------------------------------------------------

    def _apply_light_palette(self) -> None:
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#f4f6f9"))
        palette.setColor(QPalette.WindowText, QColor(TEXT_COLOR))
        palette.setColor(QPalette.Base, QColor("#ffffff"))
        palette.setColor(QPalette.AlternateBase, QColor("#f7f7f7"))
        palette.setColor(QPalette.Text, QColor(TEXT_COLOR))
        palette.setColor(QPalette.PlaceholderText, QColor(PLACEHOLDER_COLOR))
        palette.setColor(QPalette.Button, QColor("#ffffff"))
        palette.setColor(QPalette.ButtonText, QColor(TEXT_COLOR))
        palette.setColor(QPalette.Highlight, QColor(PRIMARY_BLUE))
        palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        palette.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
        palette.setColor(QPalette.ToolTipText, QColor(TEXT_COLOR))
        self.setPalette(palette)
        app = QApplication.instance()
        if app is not None:
            app.setPalette(palette)

    def _apply_active_peer(self, peer: Optional[PeerInfo]) -> None:
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
            self.chat_avatar_label.setPixmap(_build_avatar_pixmap("LAN", size=46, status=None, avatar_index=1))
            self.channel_tag_label.setText("# General")
            return
        if peers is None:
            peers = self.shared_state.get_online_peers()
        peer = next((p for p in peers if p.peer_id == self._active_peer_id), None)
        name = self._peer_display_name(self._active_peer_id)
        self.chat_header_label.setText(f"Chatting with {name}")
        self.channel_tag_label.setText(f"# {name}")
        if peer is None:
            self.chat_sub_label.setText(f"{self._active_peer_id} \u00b7 no presence broadcast (may be offline)")
            self.chat_avatar_label.setPixmap(_build_avatar_pixmap(name, size=46, status="offline"))
        else:
            self.chat_sub_label.setText(
                f'{peer.ip}:{peer.tcp_port} \u00b7 <span style="color:{STATUS_COLORS.get(peer.status, OFFLINE_COLOR)}">'
                f"\u25cf</span> {peer.status}"
            )
            self.chat_avatar_label.setPixmap(_build_avatar_pixmap(peer.name, size=46, status=peer.status))

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
        if message.is_recalled:
            return f'<span style="color:#8c97ac;">{timestamp} [{html.escape(message.sender_name)}] {content}</span>'
        color = PRIMARY_BLUE if message.sender_id == SELF_SENDER_ID else PEER_COLOR
        return (
            f'<span style="color:#a1a1bc;">{timestamp}</span> '
            f'<b style="color:{color};">[{html.escape(message.sender_name)}]</b> '
            f'<span style="color:{TEXT_COLOR};">{content}</span>'
        )

    @staticmethod
    def _escape_multiline(text: str) -> str:
        """Escape HTML, giữ xuống dòng và khoảng trắng liên tiếp (để bảng /list thẳng cột)."""
        escaped = html.escape(text)
        escaped = escaped.replace("  ", "&nbsp;&nbsp;")
        return escaped.replace("\n", "<br>")
