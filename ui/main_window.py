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
import shutil
import time
from typing import Callable, Dict, List, Optional, Set, Tuple

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
    Slot,
)
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
    QResizeEvent,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
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

from core.models import REACT_PREFIX, RECALL_PREFIX, REPLY_PREFIX, ChatMessage, PeerInfo
from core.shared_state import SharedState
from ui.command_parser import SELF_SENDER_ID, CommandParser, format_size
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

DEFAULT_AVATAR_FILE = "default_avatar.png"
AVATAR_FILES = [DEFAULT_AVATAR_FILE]
AVATAR_FALLBACK_COLORS = [
    "#555555",
]

EMOJI_LIST = [
    "😀", "😄", "😁", "😆", "😂", "🤣", "😊",
    "😇", "🙂", "😉", "😍", "🥰", "😘", "😋",
    "😜", "🤪", "😎", "🤩", "🥳", "😏", "🤔",
    "🤗", "🤫", "😮", "😢", "😭", "😤", "🤯",
    "👍", "👎", "👏", "🙌", "🤝", "🙏", "💪",
    "❤️", "🧡", "💛", "💚", "💙", "🔥", "🎉",
]

REACTION_EMOJIS = ["❤️", "😆", "😮", "😢", "😡", "👍"]

SLASH_COMMANDS: List[Tuple[str, str, bool]] = [
    ("/list", "Hiển thị danh sách người dùng đang online", True),
    ("/chat ", "Mở cuộc trò chuyện với người dùng (/chat <tên|số>)", False),
    ("/send ", "Gửi tệp đính kèm cho người đang chat (/send <file>)", False),
    ("/status online", "Đặt trạng thái Trực tuyến (Online)", True),
    ("/status away", "Đặt trạng thái Vắng mặt (Away)", True),
    ("/leave", "Rời khỏi cuộc trò chuyện hiện tại", True),
    ("/help", "Xem bảng hướng dẫn toàn bộ các lệnh", True),
    ("/quit", "Đóng kết nối và thoát ứng dụng", True),
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
QWidget#profileCard:hover {
    background: #f2f7ff;
    border: 1px solid #cfe0fa;
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
QLineEdit#searchInput:hover {
    background: #f9fbff;
    border: 1px solid #b8d2f8;
}
QLineEdit#searchInput:focus {
    background: #ffffff;
    border: 1.5px solid #2f80ed;
}
QPushButton#filterPillActive {
    background: #2f80ed;
    color: #ffffff;
    border: 1px solid #2f80ed;
    border-radius: 8px;
    padding: 5px 10px;
    font-size: 11px;
    font-weight: 700;
}
QPushButton#filterPillActive:hover {
    background: #1f6fd8;
    border: 1px solid #1f6fd8;
}
QPushButton#filterPillInactive {
    background: #ffffff;
    color: #4f5e7b;
    border: 1px solid #e6ecf5;
    border-radius: 8px;
    padding: 5px 10px;
    font-size: 11px;
    font-weight: 600;
}
QPushButton#filterPillInactive:hover {
    background: #f2f7ff;
    color: #2f80ed;
    border: 1px solid #cfe0fa;
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
    border: 1px solid transparent;
}
QListWidget#peerList::item:hover {
    background: #eef5ff;
    border: 1px solid #d4e5fc;
}
QListWidget#peerList::item:selected {
    background: #eaf2fd;
    color: #1b1a57;
    border: 1px solid #bdd7fb;
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
QFrame#bubbleSelf:hover {
    background: #2576e4;
}
QFrame#bubblePeer {
    background: #f7f7f7;
    border: 1px solid #eceff4;
    border-radius: 16px;
}
QFrame#bubblePeer:hover {
    background: #f1f5fb;
    border: 1px solid #dce6f5;
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
    background: #f0f4fa;
    color: #5c6b8a;
    border: 1px solid #e1e8f5;
    border-radius: 15px;
    font-size: 19px;
    font-weight: 800;
    min-width: 30px;
    max-width: 30px;
    min-height: 30px;
    max-height: 30px;
    padding: 0px 0px 3px 0px;
}
QPushButton#bubbleMenuBtn:hover {
    background: #eaf2fd;
    color: #2f80ed;
    border: 1px solid #b8d4fb;
}
QPushButton#bubbleMenuBtn:pressed {
    background: #d5e6fb;
    padding-top: 2px;
}
QPushButton#bubbleActionBtn {
    background: #f0f4fa;
    color: #5c6b8a;
    border: 1px solid #e1e8f5;
    border-radius: 15px;
    font-size: 14px;
    font-weight: 700;
    min-width: 30px;
    max-width: 30px;
    min-height: 30px;
    max-height: 30px;
    padding: 0px;
}
QPushButton#bubbleActionBtn:hover {
    background: #eaf2fd;
    color: #2f80ed;
    border: 1px solid #b8d4fb;
}
QPushButton#bubbleActionBtn:pressed {
    background: #d5e6fb;
    padding-top: 2px;
}
QPushButton#bubbleCornerReactBtn {
    background: #ffffff;
    color: #5c6b8a;
    border: 1px solid #dce3ee;
    border-radius: 12px;
    font-size: 13px;
    min-width: 24px;
    max-width: 24px;
    min-height: 24px;
    max-height: 24px;
    padding: 0px;
}
QPushButton#bubbleCornerReactBtn:hover {
    background: #eaf2fd;
    border: 1px solid #2f80ed;
}
QPushButton#bubbleCornerReactBtn:pressed {
    background: #d5e6fb;
}
QLabel#reactionBadge {
    background: #ffffff;
    color: #1b1a57;
    border: 1px solid #dce3ee;
    border-radius: 11px;
    padding: 1px 8px;
    font-size: 11px;
    font-weight: 700;
    min-height: 20px;
    max-height: 22px;
}
QFrame#quoteSelf {
    background: rgba(255, 255, 255, 0.16);
    border-left: 3px solid #ffffff;
    border-radius: 6px;
}
QFrame#quotePeer {
    background: #eef3fb;
    border-left: 3px solid #2f80ed;
    border-radius: 6px;
}
QFrame#replyPreviewBar {
    background: #f5f8ff;
    border-top: 1px solid #dce6f7;
    border-bottom: 1px solid #eaeef4;
}
QFrame#replyAccentLine {
    background: #2f80ed;
    border-radius: 2px;
    min-width: 3px;
    max-width: 3px;
}
QPushButton#replyCloseBtn {
    background: transparent;
    color: #7c88a1;
    border: none;
    border-radius: 13px;
    font-size: 14px;
    font-weight: 700;
    min-width: 26px;
    max-width: 26px;
    min-height: 26px;
    max-height: 26px;
    padding: 0px;
}
QPushButton#replyCloseBtn:hover {
    background: #eaf2fd;
    color: #eb5757;
}
QFrame#cmdSuggestPopup {
    background: #ffffff;
    border: 1px solid #cfe0fa;
    border-radius: 14px;
}
QLabel#cmdSuggestHeader {
    color: #2f80ed;
    font-size: 11px;
    font-weight: 700;
    padding: 4px 10px 2px 10px;
}
QListWidget#cmdSuggestList {
    background: transparent;
    border: none;
    outline: 0;
    color: #1b1a57;
    font-size: 12px;
}
QListWidget#cmdSuggestList::item {
    border-radius: 8px;
    padding: 6px 10px;
    margin: 1px 4px;
    color: #1b1a57;
}
QListWidget#cmdSuggestList::item:hover {
    background: #f2f7fe;
}
QListWidget#cmdSuggestList::item:selected {
    background: #eaf2fd;
    color: #2f80ed;
    font-weight: 700;
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
QLineEdit#messageInput:hover {
    background: #fafcff;
    border: 1px solid #b8d2f8;
}
QLineEdit#messageInput:focus {
    background: #ffffff;
    border: 1.5px solid #2f80ed;
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
QPushButton:pressed {
    background: #185abc;
    padding-top: 8px;
    padding-bottom: 6px;
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
    border: 1px solid #c9defc;
}
QPushButton#emojiButton:pressed, QPushButton#sendFileButton:pressed {
    background: #d5e6fb;
    padding-top: 2px;
}
QPushButton#sendFileButton:disabled {
    background: transparent;
}
QPushButton#leaveButton {
    background: #fff3f3;
    color: #eb5757;
    border: 1px solid #fad2d2;
    border-radius: 10px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#leaveButton:hover {
    background: #eb5757;
    color: #ffffff;
    border: 1px solid #eb5757;
}
QPushButton#leaveButton:pressed {
    background: #d64545;
    color: #ffffff;
    padding-top: 7px;
    padding-bottom: 5px;
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
    padding: 5px 24px 5px 10px;
    border: 1px solid #dce3ee;
    border-radius: 13px;
    background: #ffffff;
    color: #1b1a57;
    font-size: 12px;
    font-weight: 600;
    min-height: 18px;
    min-width: 64px;
}
QComboBox:hover {
    border: 1px solid #2f80ed;
    background: #f8fbff;
}
QComboBox:on {
    border: 1px solid #2f80ed;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 22px;
    border: none;
    background: transparent;
    border-top-right-radius: 13px;
    border-bottom-right-radius: 13px;
}
QComboBox::down-arrow {
    image: url(__CHEVRON_ICON_PATH__);
    width: 11px;
    height: 11px;
}
QComboBox QAbstractItemView {
    background: #ffffff;
    color: #1b1a57;
    border: 1px solid #dce3ee;
    border-radius: 10px;
    padding: 4px;
    outline: 0;
    selection-background-color: #eaf2fd;
    selection-color: #1b1a57;
}
QPushButton#fileDownloadBtn {
    background: #2f80ed;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#fileDownloadBtn:hover {
    background: #1f6fd8;
}
QPushButton#fileDownloadBtn:pressed {
    background: #185abc;
    padding-top: 6px;
    padding-bottom: 4px;
}
QPushButton#fileDownloadBtnDone {
    background: #e8f5e9;
    color: #1e7e34;
    border: 1px solid #c3e6cb;
    border-radius: 8px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 600;
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

    avatar_path = (
        custom_image_path
        if (custom_image_path and os.path.exists(custom_image_path))
        else _asset_path(DEFAULT_AVATAR_FILE)
    )

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
        bg_color = QColor("#616161")
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
    Widget Bong bóng Tin nhắn bo góc tròn thật sự (border-radius: 16px) theo thiết kế Zalo:
    - Nút mặt cười nằm đè ở góc dưới cùng bên phải của khung bong bóng tin nhắn;
      khi thả cảm xúc (❤️ 😆 😮 😢 😡 👍) thì hình cảm xúc đó đè lên chính nút mặt cười
      (kèm huy hiệu đếm số lượng bên cạnh) và đồng bộ 2 chiều qua TCP.
    - Bên cạnh bong bóng là 3 nút tròn thao tác nhanh:
      + '❝' Nhắc lại / Trả lời tin nhắn (Reply)
      + '➦' Chuyển tiếp tin nhắn cho người khác (Forward)
      + '⋯' Tùy chọn thêm (Thu hồi / Xóa ở phía bạn)
    """

    def __init__(
        self,
        message: ChatMessage,
        is_self: bool,
        on_delete_for_me: Callable[[ChatMessage], None],
        on_recall_message: Callable[[ChatMessage], None],
        on_react_message: Optional[Callable[[ChatMessage, str], None]] = None,
        on_reply_message: Optional[Callable[[ChatMessage], None]] = None,
        on_forward_message: Optional[Callable[[ChatMessage], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.message = message
        self.is_self = is_self
        self._on_delete_for_me = on_delete_for_me
        self._on_recall_message = on_recall_message
        self._on_react_message = on_react_message
        self._on_reply_message = on_reply_message
        self._on_forward_message = on_forward_message

        self.outer_layout = QHBoxLayout(self)
        self.outer_layout.setContentsMargins(4, 3, 4, 3)
        self.outer_layout.setSpacing(6)

        # Khung chồng 2 lớp (QGridLayout cell 0,0) để nút mặt cười nằm đè đúng góc dưới phải của bong bóng
        self.bubble_stack = QWidget(self)
        self.bubble_grid = QGridLayout(self.bubble_stack)
        self.bubble_grid.setContentsMargins(0, 0, 0, 0)
        self.bubble_grid.setSpacing(0)

        self.bubble_pad = QWidget(self.bubble_stack)
        self.bubble_pad_layout = QVBoxLayout(self.bubble_pad)
        self.bubble_pad_layout.setContentsMargins(0, 0, 4, 11)
        self.bubble_pad_layout.setSpacing(0)

        self.bubble_frame = QFrame(self.bubble_pad)
        self.bubble_frame.setMaximumWidth(480)
        self.bubble_frame.setMinimumWidth(110)
        self.bubble_layout = QVBoxLayout(self.bubble_frame)
        self.bubble_layout.setContentsMargins(14, 10, 14, 12)
        self.bubble_layout.setSpacing(5)

        # Khung trích dẫn tin nhắn được nhắc lại (Reply Quote Box)
        self.quote_frame = QFrame(self.bubble_frame)
        self.quote_frame.setVisible(False)
        quote_layout = QVBoxLayout(self.quote_frame)
        quote_layout.setContentsMargins(8, 5, 8, 5)
        quote_layout.setSpacing(2)
        self.quote_title_label = QLabel("\u275d Reply", self.quote_frame)
        self.quote_body_label = QLabel(self.quote_frame)
        self.quote_body_label.setWordWrap(True)
        quote_layout.addWidget(self.quote_title_label)
        quote_layout.addWidget(self.quote_body_label)
        self.bubble_layout.addWidget(self.quote_frame)

        self.content_label = QLabel(self.bubble_frame)
        self.content_label.setWordWrap(True)
        self.content_label.setTextFormat(Qt.RichText)
        self.content_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.bubble_layout.addWidget(self.content_label)

        self.download_btn = QPushButton("\u2b07  Tải về", self.bubble_frame)
        self.download_btn.setObjectName("fileDownloadBtn")
        self.download_btn.setCursor(Qt.PointingHandCursor)
        self.download_btn.setVisible(False)
        self.download_btn.clicked.connect(self._on_download_clicked)
        self.bubble_layout.addWidget(self.download_btn, 0, Qt.AlignLeft)

        self.time_label = QLabel(self.bubble_frame)
        self.time_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.bubble_layout.addWidget(self.time_label)

        self.bubble_pad_layout.addWidget(self.bubble_frame)
        self.bubble_grid.addWidget(self.bubble_pad, 0, 0)

        # Cụm nút mặt cười + huy hiệu cảm xúc đè ở góc dưới cùng bên phải của bong bóng
        self.corner_react_bar = QWidget(self.bubble_stack)
        self.corner_react_layout = QHBoxLayout(self.corner_react_bar)
        self.corner_react_layout.setContentsMargins(0, 0, 8, 0)
        self.corner_react_layout.setSpacing(4)

        self.reaction_badge = QLabel(self.corner_react_bar)
        self.reaction_badge.setObjectName("reactionBadge")
        self.reaction_badge.setVisible(False)
        self.corner_react_layout.addWidget(self.reaction_badge, 0, Qt.AlignVCenter)

        self.react_btn = QPushButton("", self.corner_react_bar)
        self.react_btn.setObjectName("bubbleCornerReactBtn")
        self.react_btn.setCursor(Qt.PointingHandCursor)
        self.react_btn.setToolTip("Thả cảm xúc vào tin nhắn")
        self.react_btn.clicked.connect(self._show_reaction_picker)
        self.corner_react_layout.addWidget(self.react_btn, 0, Qt.AlignVCenter)

        self.bubble_grid.addWidget(
            self.corner_react_bar,
            0,
            0,
            Qt.AlignBottom | Qt.AlignRight,
        )

        # 3 nút tròn thao tác bên cạnh bong bóng: Nhắc lại (❝), Chuyển tiếp (➦), Tùy chọn (⋯)
        self.reply_btn = QPushButton("\u275d", self)
        self.reply_btn.setObjectName("bubbleActionBtn")
        self.reply_btn.setCursor(Qt.PointingHandCursor)
        self.reply_btn.setToolTip("Nhắc lại tin nhắn (Reply)")
        self.reply_btn.clicked.connect(self._trigger_reply)

        self.forward_btn = QPushButton("\u27a6", self)
        self.forward_btn.setObjectName("bubbleActionBtn")
        self.forward_btn.setCursor(Qt.PointingHandCursor)
        self.forward_btn.setToolTip("Chuyển tiếp tin nhắn (Forward)")
        self.forward_btn.clicked.connect(self._trigger_forward)

        self.menu_btn = QPushButton("\u22ef", self)
        self.menu_btn.setObjectName("bubbleMenuBtn")
        self.menu_btn.setCursor(Qt.PointingHandCursor)
        self.menu_btn.setToolTip("Tùy chọn tin nhắn (Xóa / Thu hồi)")
        self.menu_btn.clicked.connect(self._show_actions_menu)

        if is_self:
            self.outer_layout.addStretch(1)
            self.outer_layout.addWidget(self.reply_btn, 0, Qt.AlignVCenter)
            self.outer_layout.addWidget(self.forward_btn, 0, Qt.AlignVCenter)
            self.outer_layout.addWidget(self.menu_btn, 0, Qt.AlignVCenter)
            self.outer_layout.addWidget(self.bubble_stack, 0)
        else:
            self.outer_layout.addWidget(self.bubble_stack, 0)
            self.outer_layout.addWidget(self.reply_btn, 0, Qt.AlignVCenter)
            self.outer_layout.addWidget(self.forward_btn, 0, Qt.AlignVCenter)
            self.outer_layout.addWidget(self.menu_btn, 0, Qt.AlignVCenter)
            self.outer_layout.addStretch(1)

        self.refresh_appearance()

    def refresh_appearance(self) -> None:
        """Cập nhật giao diện bong bóng (trích dẫn reply, thẻ file, cảm xúc góc dưới phải hoặc thu hồi)."""
        timestamp = time.strftime("%H:%M:%S", time.localtime(self.message.timestamp))
        reply_quote = getattr(self.message, "reply_to_text", "") or ""

        if self.message.is_recalled:
            self.bubble_frame.setObjectName("bubbleRecalled")
            self.quote_frame.setVisible(False)
            self.download_btn.setVisible(False)
            self.react_btn.setVisible(False)
            self.reaction_badge.setVisible(False)
            self.reply_btn.setVisible(False)
            self.forward_btn.setVisible(False)
            recalled_text = (
                "Bạn đã thu hồi một tin nhắn"
                if self.is_self
                else "Tin nhắn đã được thu hồi"
            )
            self.content_label.setText(
                f'<span style="color:#8c97ac; font-style:italic; font-size:13px;">'
                f"\U0001f6ab {recalled_text}</span>"
            )
            self.time_label.setText(timestamp)
            self.time_label.setStyleSheet("color: #a1a1bc; font-size: 10px;")
        else:
            self.react_btn.setVisible(True)
            self.reply_btn.setVisible(True)
            self.forward_btn.setVisible(True)

            if reply_quote:
                self.quote_frame.setObjectName("quoteSelf" if self.is_self else "quotePeer")
                title_col = "#ffffff" if self.is_self else "#2f80ed"
                body_col = "#eaf2fd" if self.is_self else "#4f5e7b"
                self.quote_title_label.setStyleSheet(f"color: {title_col}; font-size: 11px; font-weight: 700;")
                self.quote_body_label.setStyleSheet(f"color: {body_col}; font-size: 12px;")
                self.quote_body_label.setText(reply_quote)
                self.quote_frame.setVisible(True)
                self.quote_frame.style().unpolish(self.quote_frame)
                self.quote_frame.style().polish(self.quote_frame)
            else:
                self.quote_frame.setVisible(False)

            if getattr(self.message, "is_file", False):
                fname = html.escape(self.message.file_name or self.message.content)
                fsize = format_size(getattr(self.message, "file_size", 0))
                if self.is_self:
                    self.bubble_frame.setObjectName("bubbleSelf")
                    self.download_btn.setVisible(False)
                    self.content_label.setText(
                        f'<div style="color:#ffffff; font-size:13px; font-weight:700;">\U0001f4c4 {fname}</div>'
                        f'<div style="color:#d5e6fb; font-size:11px; margin-top:2px;">Dung lượng: {fsize} \u2022 Đã gửi tệp</div>'
                    )
                    self.time_label.setText(timestamp)
                    self.time_label.setStyleSheet("color: #d5e6fb; font-size: 10px;")
                else:
                    self.bubble_frame.setObjectName("bubblePeer")
                    self.download_btn.setVisible(True)
                    self.content_label.setText(
                        f'<div style="color:{TEXT_COLOR}; font-size:13px; font-weight:700;">\U0001f4c4 {fname}</div>'
                        f'<div style="color:{TEXT_SECONDARY}; font-size:11px; margin-top:2px;">Dung lượng: {fsize}</div>'
                    )
                    self.time_label.setText(timestamp)
                    self.time_label.setStyleSheet(f"color: {PLACEHOLDER_COLOR}; font-size: 10px;")
            elif self.is_self:
                self.bubble_frame.setObjectName("bubbleSelf")
                self.download_btn.setVisible(False)
                escaped_body = MainWindow._escape_multiline(self.message.content)
                self.content_label.setText(
                    f'<span style="color:#ffffff; font-size:13px; line-height:18px;">{escaped_body}</span>'
                )
                self.time_label.setText(timestamp)
                self.time_label.setStyleSheet("color: #d5e6fb; font-size: 10px;")
            else:
                self.bubble_frame.setObjectName("bubblePeer")
                self.download_btn.setVisible(False)
                escaped_body = MainWindow._escape_multiline(self.message.content)
                self.content_label.setText(
                    f'<span style="color:{TEXT_COLOR}; font-size:13px; line-height:18px;">{escaped_body}</span>'
                )
                self.time_label.setText(timestamp)
                self.time_label.setStyleSheet(f"color: {PLACEHOLDER_COLOR}; font-size: 10px;")

            # Cập nhật nút mặt cười ở góc dưới phải bong bóng:
            # Khi đã thả cảm xúc, hình cảm xúc đè trực tiếp lên nút mặt cười + hiện huy hiệu đếm bên cạnh
            reactions = getattr(self.message, "reactions", {}) or {}
            emojis = [e for e in reactions.values() if e]
            if emojis:
                my_react = reactions.get(SELF_SENDER_ID, "")
                top_emoji = my_react or emojis[-1]
                self.react_btn.setIcon(QIcon())
                self.react_btn.setText(top_emoji)
                unique_emojis = list(dict.fromkeys(emojis))
                self.reaction_badge.setText(f"{' '.join(unique_emojis)} {len(emojis)}")
                self.reaction_badge.setVisible(True)
            else:
                self.react_btn.setText("")
                self.react_btn.setIcon(QIcon(_load_svg_pixmap("icon_emoji.svg", 14, 14)))
                self.react_btn.setIconSize(QSize(14, 14))
                self.reaction_badge.setVisible(False)

        self.bubble_frame.style().unpolish(self.bubble_frame)
        self.bubble_frame.style().polish(self.bubble_frame)

    @Slot()
    def _trigger_reply(self) -> None:
        if not self.message.is_recalled and self._on_reply_message is not None:
            self._on_reply_message(self.message)

    @Slot()
    def _trigger_forward(self) -> None:
        if not self.message.is_recalled and self._on_forward_message is not None:
            self._on_forward_message(self.message)

    @Slot()
    def _show_reaction_picker(self) -> None:
        """Hiển thị thanh 6 cảm xúc nhanh (❤️ 😆 😮 😢 😡 👍) ngay phía trên nút mặt cười."""
        if self.message.is_recalled:
            return
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #ffffff; border: 1px solid #cfe0fa; border-radius: 20px; padding: 4px 6px; }"
        )
        bar = QWidget(menu)
        row = QHBoxLayout(bar)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(4)

        current_my_react = (getattr(self.message, "reactions", {}) or {}).get(SELF_SENDER_ID, "")
        for emoji_char in REACTION_EMOJIS:
            btn = QPushButton(emoji_char, bar)
            btn.setFixedSize(34, 34)
            btn.setCursor(Qt.PointingHandCursor)
            is_selected = emoji_char == current_my_react
            bg = "#eaf2fd" if is_selected else "transparent"
            border = "1px solid #2f80ed" if is_selected else "1px solid transparent"
            btn.setStyleSheet(
                f"QPushButton {{ background: {bg}; border: {border}; border-radius: 17px; font-size: 18px; padding: 0; }}"
                "QPushButton:hover { background: #eaf2fd; border: 1px solid #9ec5fa; }"
                "QPushButton:pressed { background: #d5e6fb; padding-top: 2px; }"
            )
            btn.clicked.connect(
                lambda _checked=False, e=emoji_char, m=menu: self._pick_reaction(e, m)
            )
            row.addWidget(btn)

        action = QWidgetAction(menu)
        action.setDefaultWidget(bar)
        menu.addAction(action)

        hint_w = bar.sizeHint().width() + 12
        hint_h = bar.sizeHint().height() + 12
        pos = self.react_btn.mapToGlobal(QPoint((self.react_btn.width() - hint_w) // 2, -hint_h - 4))
        menu.exec(pos)

    def _pick_reaction(self, emoji_char: str, menu: QMenu) -> None:
        menu.close()
        if self._on_react_message is not None:
            self._on_react_message(self.message, emoji_char)

    @Slot()
    def _on_download_clicked(self) -> None:
        """Mở hộp thoại cho phép người dùng chủ động chọn nơi tải file về máy tính."""
        src_path = getattr(self.message, "file_path", "")
        fname = getattr(self.message, "file_name", "") or self.message.content or "downloaded_file"
        default_dir = os.path.abspath("downloads")
        os.makedirs(default_dir, exist_ok=True)
        default_target = os.path.join(default_dir, os.path.basename(fname))

        dest_path, _ = QFileDialog.getSaveFileName(
            self,
            "Tải file về máy tính",
            default_target,
            "All Files (*)",
        )
        if not dest_path:
            return
        try:
            if src_path and os.path.isfile(src_path):
                if os.path.abspath(src_path) != os.path.abspath(dest_path):
                    shutil.copy2(src_path, dest_path)
            else:
                with open(dest_path, "wb") as f:
                    f.write(b"")
            self.download_btn.setText("\u2713  Đã tải về")
            self.download_btn.setObjectName("fileDownloadBtnDone")
            self.download_btn.setToolTip(f"Đã lưu tại: {dest_path}")
            self.download_btn.style().unpolish(self.download_btn)
            self.download_btn.style().polish(self.download_btn)
        except OSError:
            pass

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # noqa: N802
        self._open_menu_at(event.globalPos())
        event.accept()

    @Slot()
    def _show_actions_menu(self) -> None:
        pos = self.menu_btn.mapToGlobal(QPoint(0, self.menu_btn.height()))
        self._open_menu_at(pos)

    def _open_menu_at(self, global_pos: QPoint) -> None:
        menu = QMenu(self)
        if not self.message.is_recalled:
            reply_action = QAction("\u275d  Nhắc lại tin nhắn (Reply)", menu)
            reply_action.triggered.connect(self._trigger_reply)
            menu.addAction(reply_action)

            forward_action = QAction("\u27a6  Chuyển tiếp tin nhắn (Forward)...", menu)
            forward_action.triggered.connect(self._trigger_forward)
            menu.addAction(forward_action)
            menu.addSeparator()

        if self.is_self and not self.message.is_recalled:
            recall_action = QAction("\u21a9\ufe0f  Thu hồi tin nhắn (với mọi người)", menu)
            recall_action.triggered.connect(lambda: self._on_recall_message(self.message))
            menu.addAction(recall_action)

        delete_action = QAction("\U0001f5d1\ufe0f  Xóa ở phía bạn", menu)
        delete_action.triggered.connect(lambda: self._on_delete_for_me(self.message))
        menu.addAction(delete_action)
        menu.exec(global_pos)


class ForwardMessageDialog(QDialog):
    """
    Hộp thoại 'Chuyển tiếp tin nhắn' cho phép tìm kiếm và chọn 1 hoặc nhiều người nhận
    đang online để chuyển tiếp nhanh tin nhắn văn bản hoặc tệp đính kèm.
    """

    def __init__(
        self,
        message: ChatMessage,
        peers: List[PeerInfo],
        on_forward: Callable[[ChatMessage, List[PeerInfo]], None],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.message = message
        self.peers = list(peers)
        self._on_forward = on_forward
        self._checkboxes: List[Tuple[PeerInfo, QCheckBox]] = []

        self.setWindowTitle("Chuyển tiếp tin nhắn")
        self.setMinimumSize(400, 420)
        self.setStyleSheet(
            "QDialog { background: #ffffff; color: #1b1a57; }"
            "QLabel { color: #1b1a57; }"
            "QCheckBox { color: #1b1a57; font-size: 13px; padding: 6px 8px; spacing: 8px; }"
            "QCheckBox:hover { background: #f2f7fe; border-radius: 8px; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("\u27a6 Chuyển tiếp tin nhắn tới bạn bè")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #1b1a57;")
        layout.addWidget(title)

        preview_box = QFrame(self)
        preview_box.setStyleSheet(
            "QFrame { background: #f5f8ff; border: 1px solid #dce6f7; border-left: 3px solid #2f80ed; border-radius: 8px; }"
        )
        p_layout = QVBoxLayout(preview_box)
        p_layout.setContentsMargins(10, 8, 10, 8)
        preview_str = (
            f"\U0001f4c4 Tệp: {message.file_name or message.content}"
            if getattr(message, "is_file", False)
            else message.content
        )
        preview_lbl = QLabel(preview_str, preview_box)
        preview_lbl.setWordWrap(True)
        preview_lbl.setStyleSheet("color: #4f5e7b; font-size: 12px; border: none;")
        p_layout.addWidget(preview_lbl)
        layout.addWidget(preview_box)

        self.search_edit = QLineEdit(self)
        self.search_edit.setObjectName("searchInput")
        self.search_edit.setPlaceholderText("Search recipients by name or IP...")
        self.search_edit.textChanged.connect(self._filter_peers)
        layout.addWidget(self.search_edit)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 1px solid #e6ecf5; border-radius: 10px; background: #fbfcfe; }")
        list_container = QWidget(scroll)
        self.list_layout = QVBoxLayout(list_container)
        self.list_layout.setContentsMargins(8, 8, 8, 8)
        self.list_layout.setSpacing(4)

        if not self.peers:
            empty_lbl = QLabel("Hiện chưa có người dùng nào khác đang online.", list_container)
            empty_lbl.setStyleSheet("color: #8c97ac; font-size: 12px; padding: 12px;")
            self.list_layout.addWidget(empty_lbl)
        else:
            for peer in self.peers:
                cb = QCheckBox(f"{peer.name}  ({peer.ip}:{peer.tcp_port})  \u2022  {peer.status}", list_container)
                cb.setCursor(Qt.PointingHandCursor)
                self.list_layout.addWidget(cb)
                self._checkboxes.append((peer, cb))
        self.list_layout.addStretch(1)
        scroll.setWidget(list_container)
        layout.addWidget(scroll, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QPushButton("Hủy", self)
        cancel_btn.setObjectName("leaveButton")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self.send_forward_btn = QPushButton("\u27a6 Chuyển tiếp", self)
        self.send_forward_btn.setCursor(Qt.PointingHandCursor)
        self.send_forward_btn.setEnabled(bool(self.peers))
        self.send_forward_btn.clicked.connect(self._confirm_forward)
        btn_row.addWidget(self.send_forward_btn)
        layout.addLayout(btn_row)

    def _filter_peers(self, text: str) -> None:
        q = (text or "").strip().lower()
        for peer, cb in self._checkboxes:
            haystack = f"{peer.name} {peer.ip}:{peer.tcp_port} {peer.status}".lower()
            cb.setVisible(not q or q in haystack)

    def _confirm_forward(self) -> None:
        selected = [peer for peer, cb in self._checkboxes if cb.isChecked()]
        if not selected:
            return
        self._on_forward(self.message, selected)
        self.accept()


class HistoryLineEdit(QLineEdit):
    """
    Ô nhập liệu có lịch sử lệnh (Up/Down) và hỗ trợ điều hướng bảng đề xuất lệnh '/'
    ngay phía trên ô nhập.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._history: List[str] = []
        self._cursor = 0
        self._draft = ""
        self.popup_key_handler: Optional[Callable[[int], bool]] = None

    def remember(self, text: str) -> None:
        if text and (not self._history or self._history[-1] != text):
            self._history.append(text)
            del self._history[:-INPUT_HISTORY_LIMIT]
        self._cursor = len(self._history)
        self._draft = ""

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - tên hàm của Qt
        if self.popup_key_handler is not None and event.key() in (
            Qt.Key_Up,
            Qt.Key_Down,
            Qt.Key_Tab,
            Qt.Key_Escape,
        ):
            if self.popup_key_handler(event.key()):
                event.accept()
                return
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
    - Chế độ `mode="online"` (tab Online Users):
      Avatar tròn 44x44px kèm chấm trạng thái xanh lá, số thứ tự + Tên (khớp /chat <số>),
      icon check + Địa chỉ IP:Port, cột phải hiện Active/Online + unread badge.
    - Chế độ `mode="chat"` (tab All Chats):
      Kiểu Messenger: Avatar kèm chấm trạng thái online/away/offline, Tên người dùng,
      preview tin nhắn cuối cùng, cột phải hiện giờ gửi HH:MM + unread badge (hoặc nhãn Offline).
    """

    def __init__(
        self,
        index: int,
        peer: PeerInfo,
        unread: int,
        is_active: bool,
        mode: str = "online",
        last_message_preview: str = "",
        last_message_time: Optional[float] = None,
    ) -> None:
        super().__init__()
        self.setAttribute(Qt.WA_TransparentForMouseEvents)  # để click đi xuống QListWidget

        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(12)

        is_offline = peer.status == "offline"

        # 1. Avatar + Status Dot SVG
        avatar_label = QLabel()
        avatar_label.setFixedSize(44, 44)
        avatar_label.setPixmap(_build_avatar_pixmap(peer.name, size=44, status=peer.status, avatar_index=max(0, index - 1)))
        avatar_label.setToolTip(peer.status)
        outer.addWidget(avatar_label, 0, Qt.AlignVCenter)

        # 2. Tên & Dòng phụ (IP:Port ở Online Users, hoặc preview tin nhắn cuối ở All Chats)
        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(3)

        display_title = peer.name if mode == "chat" else f"{index}. {peer.name}"
        name_label = QLabel(display_title)
        name_label.setTextFormat(Qt.PlainText)
        name_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        title_color = TEXT_SECONDARY if is_offline and not is_active else TEXT_COLOR
        name_label.setStyleSheet(f"color: {title_color}; font-size: 13px;")
        name_font = name_label.font()
        name_font.setBold(True if (is_active or unread > 0) else False)
        name_font.setWeight(QFont.Bold if (is_active or unread > 0) else QFont.Medium)
        name_label.setFont(name_font)

        sub_row = QHBoxLayout()
        sub_row.setContentsMargins(0, 0, 0, 0)
        sub_row.setSpacing(4)

        if mode == "chat":
            preview_text = last_message_preview or "No messages yet"
            sub_label = QLabel(preview_text)
            sub_label.setTextFormat(Qt.PlainText)
            sub_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            sub_color = TEXT_COLOR if unread > 0 else TEXT_SECONDARY
            sub_weight = "600" if unread > 0 else "400"
            sub_label.setStyleSheet(f"color: {sub_color}; font-size: 12px; font-weight: {sub_weight};")
            sub_row.addWidget(sub_label, 1)
        else:
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

        # 3. Cột phải: Thời gian/Trạng thái + Unread Badge (#2F80ED) hoặc nhãn Offline
        right_box = QVBoxLayout()
        right_box.setContentsMargins(0, 0, 0, 0)
        right_box.setSpacing(4)
        right_box.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        if mode == "chat":
            if last_message_time is not None:
                meta_text = time.strftime("%H:%M", time.localtime(last_message_time))
            else:
                meta_text = "Active" if is_active else peer.status.capitalize()
            meta_color = PRIMARY_BLUE if (is_active or unread > 0) else PLACEHOLDER_COLOR
        else:
            meta_text = "Active" if is_active else peer.status.capitalize()
            meta_color = PRIMARY_BLUE if is_active else PLACEHOLDER_COLOR

        meta_label = QLabel(meta_text)
        meta_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        meta_label.setStyleSheet(f"color: {meta_color}; font-size: 11px; font-weight: 600;")
        right_box.addWidget(meta_label, 0, Qt.AlignRight)

        self.badge = QLabel("99+" if unread > 99 else str(unread))
        self.badge.setObjectName("unreadBadge")
        self.badge.setAlignment(Qt.AlignCenter)
        self.badge.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.badge.setVisible(unread > 0)
        right_box.addWidget(self.badge, 0, Qt.AlignRight)

        if mode == "chat" and is_offline and unread == 0:
            offline_tag = QLabel("Offline")
            offline_tag.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            offline_tag.setStyleSheet("color: #8c97ac; font-size: 10px; font-weight: 600;")
            right_box.addWidget(offline_tag, 0, Qt.AlignRight)

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
        self.all_chats_btn: QPushButton
        self.online_users_btn: QPushButton
        self.online_count_label: QPushButton
        self.my_name_label: QLabel
        self.my_avatar_label: ClickableAvatarLabel
        self.chat_avatar_label: QLabel
        self.channel_bar: QWidget
        self.channel_tag_label: QLabel
        self.cmd_popup: QFrame
        self.cmd_list: QListWidget
        self.reply_bar: QFrame
        self.reply_text_label: QLabel
        self.reply_close_btn: QPushButton
        self._replying_to_message: Optional[ChatMessage] = None
        self._active_animations: List[QPropertyAnimation] = []
        self._cmd_popup_navigated: bool = False

        # Trạng thái riêng của giao diện (chỉ truy cập từ Main Thread)
        self._active_peer_id: Optional[str] = None
        self._viewing_offline_peer_id: Optional[str] = None
        self._sidebar_tab: str = "online"                  # "online" | "all_chats"
        self._pending_sidebar_peer_id: Optional[str] = None
        self._peer_names: Dict[str, str] = {}              # cache peer_id -> tên (kể cả khi peer đã offline)
        self._known_peers: Dict[str, PeerInfo] = {}        # cache PeerInfo gần nhất (dùng khi peer offline)
        self._rendered_message_ids: Set[int] = set()       # chống hiển thị trùng 1 tin nhắn
        self._bubble_widgets: Dict[int, ChatBubbleWidget] = {}  # id(message) -> widget bong bóng
        self._deleted_for_me_ids: Set[int] = set()         # id(message) đã bấm "Xóa ở phía bạn"
        self._transfers: Dict[Tuple[str, str], int] = {}   # (peer_id, filename) -> % đang truyền
        self._finished_transfers: Set[Tuple[str, str]] = set()
        self._syncing_status = False
        self._search_filter_text: str = ""
        self._my_avatar_index: int = 1
        self._my_custom_avatar_path: Optional[str] = None

        self._sidebar_refresh_timer = QTimer(self)
        self._sidebar_refresh_timer.setSingleShot(True)
        self._sidebar_refresh_timer.timeout.connect(self.on_peer_list_updated)

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
        chevron_url = _asset_path("icon_chevron.svg").replace("\\", "/")
        self.setStyleSheet(STYLESHEET.replace("__CHEVRON_ICON_PATH__", chevron_url))

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
        self.my_avatar_label.setToolTip("Click để đổi Avatar của bạn (Chọn ảnh từ thiết bị)")
        self._refresh_my_avatar()
        profile_layout.addWidget(self.my_avatar_label, 0, Qt.AlignVCenter)

        my_info_box = QVBoxLayout()
        my_info_box.setContentsMargins(0, 0, 0, 0)
        my_info_box.setSpacing(2)
        self.my_name_label = QLabel(my_name)
        self.my_name_label.setObjectName("myNameLabel")
        self.my_name_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        my_info_box.addWidget(self.my_name_label)
        profile_layout.addLayout(my_info_box, 1)

        self.status_combo = QComboBox()
        self.status_combo.setObjectName("statusCombo")
        self.status_combo.setCursor(Qt.PointingHandCursor)
        self.status_combo.setMinimumWidth(98)
        self.status_combo.setIconSize(QSize(10, 10))
        self.status_combo.addItem(QIcon(_load_svg_pixmap("status_online.svg", 10, 10)), "online", "online")
        self.status_combo.addItem(QIcon(_load_svg_pixmap("status_away.svg", 10, 10)), "away", "away")
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
        self.search_input.setPlaceholderText("Search friends by name or IP...")
        self.search_input.setClearButtonEnabled(True)
        search_action = QAction(QIcon(_load_svg_pixmap("icon_search.svg", 16, 16)), "", self.search_input)
        self.search_input.addAction(search_action, QLineEdit.LeadingPosition)
        left_layout.addWidget(self.search_input)

        # 4. Hàng Filter Pills tương tác ("All Chats (N)" & "Online Users (M)")
        pills_row = QHBoxLayout()
        pills_row.setContentsMargins(2, 0, 2, 2)
        pills_row.setSpacing(8)

        self.all_chats_btn = QPushButton("All Chats (0)")
        self.all_chats_btn.setObjectName("filterPillInactive")
        self.all_chats_btn.setCursor(Qt.PointingHandCursor)
        self.all_chats_btn.setToolTip("Show all users you have chatted with (including offline)")
        pills_row.addWidget(self.all_chats_btn, 0)

        self.online_users_btn = QPushButton("Online Users (0)")
        self.online_users_btn.setObjectName("filterPillActive")
        self.online_users_btn.setCursor(Qt.PointingHandCursor)
        self.online_users_btn.setToolTip("Show friends currently online (status: online)")
        self.online_count_label = self.online_users_btn
        pills_row.addWidget(self.online_users_btn, 0)
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

        self.leave_btn = QPushButton(" Leave")
        self.leave_btn.setObjectName("leaveButton")
        self.leave_btn.setCursor(Qt.PointingHandCursor)
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

        # 3b. Thanh Nhắc lại tin nhắn ("❝ Reply" + nội dung trích dẫn + nút ✕ đóng) ngay phía trên ô nhập
        self.reply_bar = QFrame()
        self.reply_bar.setObjectName("replyPreviewBar")
        self.reply_bar.setVisible(False)
        reply_bar_layout = QHBoxLayout(self.reply_bar)
        reply_bar_layout.setContentsMargins(16, 8, 16, 8)
        reply_bar_layout.setSpacing(10)

        reply_accent = QFrame(self.reply_bar)
        reply_accent.setObjectName("replyAccentLine")
        reply_bar_layout.addWidget(reply_accent)

        reply_text_col = QVBoxLayout()
        reply_text_col.setContentsMargins(0, 0, 0, 0)
        reply_text_col.setSpacing(2)
        reply_header_lbl = QLabel("\u275d Reply", self.reply_bar)
        reply_header_lbl.setStyleSheet("color: #2f80ed; font-size: 12px; font-weight: 700;")
        self.reply_text_label = QLabel("", self.reply_bar)
        self.reply_text_label.setStyleSheet("color: #4f5e7b; font-size: 12px;")
        self.reply_text_label.setWordWrap(True)
        reply_text_col.addWidget(reply_header_lbl)
        reply_text_col.addWidget(self.reply_text_label)
        reply_bar_layout.addLayout(reply_text_col, 1)

        self.reply_close_btn = QPushButton("\u2715", self.reply_bar)
        self.reply_close_btn.setObjectName("replyCloseBtn")
        self.reply_close_btn.setCursor(Qt.PointingHandCursor)
        self.reply_close_btn.setToolTip("Hủy nhắc lại tin nhắn")
        self.reply_close_btn.clicked.connect(self._cancel_reply_bar)
        reply_bar_layout.addWidget(self.reply_close_btn, 0, Qt.AlignVCenter)

        right_layout.addWidget(self.reply_bar)

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
        self.message_input.installEventFilter(self)
        self.search_input.installEventFilter(self)

        # 5. Bảng đề xuất lệnh nhanh (Slash Command Suggestion Popup) nổi ngay phía trên ô nhập
        self.cmd_popup = QFrame(self)
        self.cmd_popup.setObjectName("cmdSuggestPopup")
        self.cmd_popup.setVisible(False)
        popup_shadow = QGraphicsDropShadowEffect(self.cmd_popup)
        popup_shadow.setBlurRadius(22)
        popup_shadow.setOffset(0, 4)
        popup_shadow.setColor(QColor(27, 26, 87, 45))
        self.cmd_popup.setGraphicsEffect(popup_shadow)

        popup_layout = QVBoxLayout(self.cmd_popup)
        popup_layout.setContentsMargins(6, 6, 6, 6)
        popup_layout.setSpacing(2)
        popup_header = QLabel("\u26a1 GỢI Ý LỆNH NHANH (\u2191\u2193 chọn \u2022 Tab điền \u2022 Enter/Click thực thi)", self.cmd_popup)
        popup_header.setObjectName("cmdSuggestHeader")
        popup_layout.addWidget(popup_header)

        self.cmd_list = QListWidget(self.cmd_popup)
        self.cmd_list.setObjectName("cmdSuggestList")
        self.cmd_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.cmd_list.setCursor(Qt.PointingHandCursor)
        self.cmd_list.setFocusPolicy(Qt.NoFocus)
        popup_layout.addWidget(self.cmd_list)

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
        self.message_input.textChanged.connect(self._on_message_input_text_changed)
        self.message_input.popup_key_handler = self._handle_cmd_popup_key
        self.cmd_list.itemClicked.connect(self._on_cmd_suggest_item_clicked)
        self.send_btn.clicked.connect(self._on_submit_input)
        self.send_file_btn.clicked.connect(self._on_send_file_clicked)
        self.emoji_btn.clicked.connect(self._on_emoji_clicked)
        self.my_avatar_label.clicked.connect(self._on_change_avatar_clicked)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.all_chats_btn.clicked.connect(lambda: self.set_sidebar_tab("all_chats"))
        self.online_users_btn.clicked.connect(lambda: self.set_sidebar_tab("online"))
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
        """Mở menu chọn ảnh từ thiết bị để đổi Avatar."""
        menu = QMenu(self)
        pick_file_action = QAction("\U0001f4c1  Chọn ảnh từ thiết bị", menu)
        pick_file_action.triggered.connect(self._pick_custom_avatar_file)
        menu.addAction(pick_file_action)

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
        """Lọc danh sách bạn bè / cuộc trò chuyện trên Sidebar theo tên, IP:Port hoặc nội dung tin cuối."""
        self._search_filter_text = (text or "").strip().lower()
        self.on_peer_list_updated()

    def set_sidebar_tab(self, tab: str) -> None:
        """
        Chuyển tab trên Sidebar:
        - "online": Tab Online Users — chỉ hiển thị bạn bè đang có trạng thái status == "online" (ẩn away & offline).
        - "all_chats": Tab All Chats — chỉ hiển thị tất cả người dùng đã từng nhắn tin / mở chat (gồm cả offline).
        """
        if tab not in ("online", "all_chats"):
            return
        if self._sidebar_tab == tab:
            return
        self._sidebar_tab = tab
        self._update_tab_pill_styles()
        self.on_peer_list_updated()

    def _update_tab_pill_styles(self) -> None:
        is_all_chats = self._sidebar_tab == "all_chats"
        self.all_chats_btn.setObjectName("filterPillActive" if is_all_chats else "filterPillInactive")
        self.online_users_btn.setObjectName("filterPillInactive" if is_all_chats else "filterPillActive")
        for btn in (self.all_chats_btn, self.online_users_btn):
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()

    def _schedule_sidebar_refresh(self) -> None:
        """Gộp nhiều cập nhật liên tiếp (vd khi nhận 20 tin liền nhau) để làm mới Sidebar mượt mà."""
        if not self._sidebar_refresh_timer.isActive():
            self._sidebar_refresh_timer.start(30)

    def _delete_message_for_me(self, message: ChatMessage) -> None:
        """Xóa tin nhắn ở phía mình (Delete for you)."""
        msg_id = id(message)
        self._deleted_for_me_ids.add(msg_id)
        if self._active_peer_id:
            history_list = self.shared_state.chat_histories.get(self._active_peer_id, [])
            if message in history_list:
                history_list.remove(message)
        elif self._viewing_offline_peer_id:
            history_list = self.shared_state.chat_histories.get(self._viewing_offline_peer_id, [])
            if message in history_list:
                history_list.remove(message)

        widget = self._bubble_widgets.pop(msg_id, None)
        if widget is not None:
            self.chat_bubbles_layout.removeWidget(widget)
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        self._rebuild_plain_text_mirror()
        self._schedule_sidebar_refresh()
        self.message_input.setFocus()

    def _recall_message_for_everyone(self, message: ChatMessage) -> None:
        """
        Thu hồi tin nhắn ở cả 2 phía (như Messenger):
        - Đổi bong bóng ở máy mình sang '🚫 Bạn đã thu hồi một tin nhắn' và thông báo trên khung chat.
        - Gửi khung điều khiển `__LANCHAT_RECALL__|<nội dung gốc>` qua TCP sang máy đối phương.
        """
        if message.is_recalled or message.sender_id != SELF_SENDER_ID or self._active_peer_id is None:
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
        self._schedule_sidebar_refresh()
        self.on_system_notification("[*] Bạn đã thu hồi một tin nhắn.")
        self.message_input.setFocus()

    def _react_to_message(self, message: ChatMessage, emoji_char: str) -> None:
        """
        Thả hoặc gỡ cảm xúc (❤️ 😆 😮 😢 😡 👍) trên một tin nhắn và đồng bộ 2 chiều qua TCP:
        - Nếu bấm lại đúng cảm xúc mình đã thả thì gỡ cảm xúc đó.
        - Gửi khung điều khiển `__LANCHAT_REACT__|<nội dung>|<emoji>` sang máy đối phương.
        """
        if message.is_recalled or self._active_peer_id is None:
            return
        if not hasattr(message, "reactions") or message.reactions is None:
            message.reactions = {}

        current = message.reactions.get(SELF_SENDER_ID, "")
        new_emoji = "" if current == emoji_char else emoji_char
        if new_emoji:
            message.reactions[SELF_SENDER_ID] = new_emoji
        else:
            message.reactions.pop(SELF_SENDER_ID, None)

        widget = self._bubble_widgets.get(id(message))
        if widget is not None:
            widget.refresh_appearance()

        if self._active_peer_id:
            try:
                self.command_parser.tcp_manager.send_text_message(
                    self._active_peer_id,
                    f"{REACT_PREFIX}{message.content}|{new_emoji}",
                )
            except Exception:
                pass
        self.message_input.setFocus()

    def _start_reply_to_message(self, message: ChatMessage) -> None:
        """Hiển thị thanh '❝ Reply' kèm nội dung tin nhắn được trích dẫn ngay phía trên ô nhập."""
        if message.is_recalled or self._active_peer_id is None:
            return
        self._replying_to_message = message
        raw_quote = (
            f"\U0001f4c4 {message.file_name or message.content}"
            if getattr(message, "is_file", False)
            else message.content
        )
        one_line = " ".join((raw_quote or "").splitlines()).strip()
        if len(one_line) > 120:
            one_line = one_line[:117] + "..."
        self.reply_text_label.setText(one_line)
        if not self.reply_bar.isVisible():
            self.reply_bar.setVisible(True)
            self._animate_fade_in(self.reply_bar, duration_ms=150)
        self.message_input.setFocus()

    @Slot()
    def _cancel_reply_bar(self) -> None:
        self._replying_to_message = None
        if hasattr(self, "reply_bar"):
            self.reply_bar.setVisible(False)
        self.message_input.setFocus()

    def _open_forward_dialog(self, message: ChatMessage) -> None:
        """Mở hộp thoại chọn 1 hoặc nhiều người nhận đang online để chuyển tiếp tin nhắn/tệp."""
        if message.is_recalled:
            return
        peers = self.shared_state.get_online_peers()
        dlg = ForwardMessageDialog(
            message=message,
            peers=peers,
            on_forward=self._forward_message_to_peers,
            parent=self,
        )
        dlg.exec()
        self.message_input.setFocus()

    def _forward_message_to_peers(self, message: ChatMessage, target_peers: List[PeerInfo]) -> int:
        """
        Chuyển tiếp `message` (văn bản hoặc tệp) tới danh sách `target_peers` qua TCP.
        Trả về số người nhận đã được chuyển tiếp thành công.
        """
        if message.is_recalled or not target_peers:
            return 0
        my_name, _, _ = self.shared_state.get_my_info()
        forwarded_count = 0

        for peer in target_peers:
            if not self.command_parser.tcp_manager.connect_to_peer(peer):
                continue

            if getattr(message, "is_file", False) and getattr(message, "file_path", "") and os.path.isfile(message.file_path):
                src_path = message.file_path
                fname = message.file_name or os.path.basename(src_path)
                fsize = getattr(message, "file_size", 0) or os.path.getsize(src_path)
                self.command_parser.tcp_manager.send_file_async(peer.peer_id, src_path)
                fwd_msg = ChatMessage(
                    sender_name=my_name,
                    sender_id=SELF_SENDER_ID,
                    content=fname,
                    is_file=True,
                    file_name=fname,
                    file_size=fsize,
                    file_path=src_path,
                )
                self.shared_state.append_message(peer.peer_id, fwd_msg)
                self.signals.chat_message_received.emit(peer.peer_id, fwd_msg)
                forwarded_count += 1
            else:
                text_to_send = message.content
                if self.command_parser.tcp_manager.send_text_message(peer.peer_id, text_to_send):
                    fwd_msg = ChatMessage(
                        sender_name=my_name,
                        sender_id=SELF_SENDER_ID,
                        content=text_to_send,
                    )
                    self.shared_state.append_message(peer.peer_id, fwd_msg)
                    self.signals.chat_message_received.emit(peer.peer_id, fwd_msg)
                    forwarded_count += 1

        self.on_peer_list_updated()
        return forwarded_count

    # ------------------------------------------------------------------
    # Bảng đề xuất lệnh '/' (Slash Command Autocomplete) & Hiệu ứng
    # ------------------------------------------------------------------

    @Slot(str)
    def _on_message_input_text_changed(self, text: str) -> None:
        if not text.startswith("/"):
            self.cmd_popup.setVisible(False)
            self._cmd_popup_navigated = False
            return

        query = text.lower()
        matches = [
            (cmd, desc, auto_exec)
            for cmd, desc, auto_exec in SLASH_COMMANDS
            if cmd.lower().startswith(query)
        ]
        if not matches:
            self.cmd_popup.setVisible(False)
            self._cmd_popup_navigated = False
            return

        self.cmd_list.clear()
        for cmd, desc, auto_exec in matches:
            item = QListWidgetItem(f"{cmd.strip()}   \u2014   {desc}")
            item.setData(Qt.UserRole, (cmd, auto_exec))
            self.cmd_list.addItem(item)
        self.cmd_list.setCurrentRow(0)
        self._cmd_popup_navigated = False
        self._position_cmd_popup(len(matches))
        if not self.cmd_popup.isVisible():
            self.cmd_popup.setVisible(True)
            self.cmd_popup.raise_()

    def _position_cmd_popup(self, row_count: int) -> None:
        if not hasattr(self, "cmd_popup") or not hasattr(self, "message_input"):
            return
        input_pos = self.message_input.mapTo(self, QPoint(0, 0))
        popup_w = max(360, min(540, self.message_input.width()))
        row_h = 30
        popup_h = min(260, 36 + row_count * row_h)
        x = max(12, input_pos.x())
        y = max(12, input_pos.y() - popup_h - 8)
        self.cmd_popup.setGeometry(x, y, popup_w, popup_h)

    def _handle_cmd_popup_key(self, key: int) -> bool:
        if not hasattr(self, "cmd_popup") or not self.cmd_popup.isVisible() or self.cmd_list.count() == 0:
            return False
        if key == Qt.Key_Escape:
            self.cmd_popup.setVisible(False)
            self._cmd_popup_navigated = False
            return True
        if key == Qt.Key_Up:
            row = (self.cmd_list.currentRow() - 1) % self.cmd_list.count()
            self.cmd_list.setCurrentRow(row)
            self._cmd_popup_navigated = True
            return True
        if key == Qt.Key_Down:
            row = (self.cmd_list.currentRow() + 1) % self.cmd_list.count()
            self.cmd_list.setCurrentRow(row)
            self._cmd_popup_navigated = True
            return True
        if key == Qt.Key_Tab:
            item = self.cmd_list.currentItem()
            if item is not None:
                cmd, _auto_exec = item.data(Qt.UserRole)
                self.message_input.setText(cmd)
                self.message_input.setCursorPosition(len(cmd))
                if not cmd.endswith(" "):
                    self.cmd_popup.setVisible(False)
            return True
        return False

    @Slot(QListWidgetItem)
    def _on_cmd_suggest_item_clicked(self, item: QListWidgetItem) -> None:
        self._apply_cmd_suggestion(item)

    def _apply_cmd_suggestion(self, item: Optional[QListWidgetItem]) -> bool:
        if item is None:
            return False
        cmd, auto_exec = item.data(Qt.UserRole)
        self.cmd_popup.setVisible(False)
        self._cmd_popup_navigated = False
        if auto_exec:
            self.message_input.remember(cmd.strip())
            self.message_input.clear()
            self.command_parser.handle_user_input(cmd.strip())
        else:
            self.message_input.setText(cmd)
            self.message_input.setCursorPosition(len(cmd))
        self.message_input.setFocus()
        return True

    def _animate_fade_in(self, widget: QWidget, duration_ms: int = 180) -> None:
        """Hiệu ứng chuyển cảnh Fade-in mượt mà khi xuất hiện bong bóng mới hoặc đổi khung chat."""
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(duration_ms)
        anim.setStartValue(0.15)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)

        def _cleanup() -> None:
            if anim in self._active_animations:
                self._active_animations.remove(anim)
            if widget is not None and widget.graphicsEffect() is effect:
                widget.setGraphicsEffect(None)

        anim.finished.connect(_cleanup)
        self._active_animations.append(anim)
        anim.start()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched in (getattr(self, "message_input", None), getattr(self, "search_input", None)):
            if event.type() == QEvent.FocusIn and isinstance(watched, QWidget):
                glow = QGraphicsDropShadowEffect(watched)
                glow.setBlurRadius(16)
                glow.setOffset(0, 2)
                glow.setColor(QColor(47, 128, 237, 65))
                watched.setGraphicsEffect(glow)
            elif event.type() == QEvent.FocusOut and isinstance(watched, QWidget):
                watched.setGraphicsEffect(None)
                if watched is getattr(self, "message_input", None) and hasattr(self, "cmd_popup"):
                    QTimer.singleShot(150, lambda: self.cmd_popup.setVisible(False) if not self.message_input.hasFocus() else None)
        return super().eventFilter(watched, event)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "cmd_popup") and self.cmd_popup.isVisible():
            self._position_cmd_popup(self.cmd_list.count())

    # ------------------------------------------------------------------
    # Hành động của người dùng -> CommandParser
    # ------------------------------------------------------------------

    @Slot()
    def _on_submit_input(self) -> None:
        text = self.message_input.text()
        if not text.strip():
            return
        if hasattr(self, "cmd_popup") and self.cmd_popup.isVisible() and self.cmd_list.count() > 0:
            stripped = text.strip().lower()
            known_exact = {c.strip().lower() for c, _, _ in SLASH_COMMANDS}
            if self._cmd_popup_navigated or stripped not in known_exact:
                if self._apply_cmd_suggestion(self.cmd_list.currentItem()):
                    return
            self.cmd_popup.setVisible(False)
            self._cmd_popup_navigated = False

        if self._viewing_offline_peer_id is not None and not text.strip().startswith("/"):
            name = self._peer_display_name(self._viewing_offline_peer_id)
            self.message_input.remember(text.strip())
            self.message_input.clear()
            self.on_system_notification(
                f"[!] {name} is currently offline (viewing read-only chat history). Pick an online user to chat."
            )
            self.message_input.setFocus()
            return

        if self._replying_to_message is not None and not text.strip().startswith("/"):
            reply_target = self._replying_to_message
            self._cancel_reply_bar()
            self.message_input.remember(text.strip())
            self.message_input.clear()
            self._send_reply_chat_text(text.strip(), reply_target)
            self.message_input.setFocus()
            return

        self.message_input.remember(text.strip())
        self.message_input.clear()
        self.command_parser.handle_user_input(text)
        self.message_input.setFocus()

    def _send_reply_chat_text(self, text: str, reply_target: ChatMessage) -> None:
        """Gửi tin nhắn trả lời kèm trích dẫn (`REPLY_PREFIX`) đồng bộ qua TCP."""
        peer = self.shared_state.get_active_chat()
        if peer is None:
            self.command_parser.handle_user_input(text)
            return
        raw_quote = (
            f"\U0001f4c4 {reply_target.file_name or reply_target.content}"
            if getattr(reply_target, "is_file", False)
            else reply_target.content
        )
        safe_quote = " ".join((raw_quote or "").replace("|", "\u00a6").splitlines()).strip()
        if len(safe_quote) > 120:
            safe_quote = safe_quote[:117] + "..."

        wire_payload = f"{REPLY_PREFIX}{safe_quote}|{text}"
        if not self.command_parser.tcp_manager.send_text_message(peer.peer_id, wire_payload):
            self.on_system_notification(
                f"[!] Message not delivered: connection to {peer.name} failed. Try /chat {peer.name} again."
            )
            return

        my_name, _, _ = self.shared_state.get_my_info()
        msg = ChatMessage(
            sender_name=my_name,
            sender_id=SELF_SENDER_ID,
            content=text,
            reply_to_text=safe_quote,
        )
        self.shared_state.append_message(peer.peer_id, msg)
        self.signals.chat_message_received.emit(peer.peer_id, msg)

    @Slot(QListWidgetItem)
    def _on_peer_item_activated(self, item: QListWidgetItem) -> None:
        peer_id = item.data(Qt.UserRole)
        if not peer_id or peer_id == self._active_peer_id or peer_id == self._pending_sidebar_peer_id:
            self.message_input.setFocus()
            return
        if peer_id == self._viewing_offline_peer_id and self.shared_state.find_peer(peer_id) is None:
            self.message_input.setFocus()
            return
        self._pending_sidebar_peer_id = peer_id
        QTimer.singleShot(0, lambda: self._open_chat_from_sidebar(peer_id))

    def _open_chat_from_sidebar(self, peer_id: str) -> None:
        self._pending_sidebar_peer_id = None
        online_peer = self.shared_state.find_peer(peer_id)
        if online_peer is not None:
            if peer_id != self._active_peer_id:
                self._viewing_offline_peer_id = None
                self.command_parser.handle_user_input(f"/chat {peer_id}")
                if self._active_peer_id != peer_id:
                    self.on_peer_list_updated()
        else:
            self._open_offline_history(peer_id)
        self.message_input.setFocus()

    def _open_offline_history(self, peer_id: str) -> None:
        """
        Mở lại lịch sử trò chuyện ở chế độ chỉ đọc (Read-only) khi người dùng click
        vào một cuộc trò chuyện đã Offline trong tab All Chats.
        """
        unread = self.shared_state.get_unread_count(peer_id)
        history = self.shared_state.set_active_chat(peer_id)
        # Đặt lại active_chat về None ở tầng SharedState để tránh gửi nhầm lên socket đã đóng
        self.shared_state.set_active_chat(None)

        self._cancel_reply_bar()
        self._clear_chat_widgets()
        self.chat_display.clear()
        self._rendered_message_ids.clear()
        self._active_peer_id = None
        self._viewing_offline_peer_id = peer_id

        self.leave_btn.setEnabled(False)
        self.send_file_btn.setEnabled(False)
        self.message_input.setPlaceholderText(
            "This user is offline (read-only history). Switch to Online Users or type a command..."
        )
        self._refresh_chat_header()
        self._update_window_title()

        messages = [m for m in list(history or []) if id(m) not in self._deleted_for_me_ids]
        first_unread = len(messages) - unread if 0 < unread <= len(messages) else None
        for index, message in enumerate(messages):
            if index == first_unread:
                self._add_unread_separator_widget(unread)
                self._append_html(
                    f'<span style="color:{ERROR_COLOR};">\u2500\u2500\u2500\u2500  {unread} unread  \u2500\u2500\u2500\u2500</span>'
                )
            self._rendered_message_ids.add(id(message))
            if isinstance(message, ChatMessage):
                self._add_message_bubble(message, animate=False)
            self._append_html(self._format_message(message))
        self._animate_fade_in(self.chat_canvas, duration_ms=180)
        self.on_peer_list_updated()

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

    def _build_offline_peer_info(self, peer_id: str, messages: List[ChatMessage]) -> PeerInfo:
        cached = self._known_peers.get(peer_id)
        if cached is not None:
            return PeerInfo(name=cached.name, ip=cached.ip, tcp_port=cached.tcp_port, status="offline")
        ip, port = peer_id, 0
        if ":" in peer_id:
            host_part, port_part = peer_id.rsplit(":", 1)
            ip = host_part
            port = int(port_part) if port_part.isdigit() else 0
        name = self._peer_names.get(peer_id)
        if not name:
            for msg in reversed(messages):
                if not msg.is_system and msg.sender_id != SELF_SENDER_ID and msg.sender_name:
                    name = msg.sender_name
                    break
        name = name or peer_id
        self._peer_names[peer_id] = name
        return PeerInfo(name=name, ip=ip, tcp_port=port, status="offline")

    def _format_last_message_preview(self, message: Optional[ChatMessage]) -> str:
        if message is None:
            return "Start chatting..."
        if getattr(message, "is_recalled", False):
            raw = message.content or "Message recalled"
        elif getattr(message, "is_file", False):
            fname = getattr(message, "file_name", "") or message.content
            prefix = "You: " if message.sender_id == SELF_SENDER_ID else ""
            raw = f"{prefix}\U0001f4c4 {fname}"
        else:
            prefix = "You: " if message.sender_id == SELF_SENDER_ID else ""
            raw = f"{prefix}{message.content}"
        one_line = " ".join((raw or "").splitlines()).strip()
        if len(one_line) > 36:
            return one_line[:33] + "..."
        return one_line

    def _collect_all_chat_entries(
        self,
        online_by_id: Dict[str, PeerInfo],
    ) -> List[Tuple[PeerInfo, Optional[ChatMessage], float]]:
        """
        Tổng hợp danh sách tất cả cuộc trò chuyện cho tab All Chats:
        - Gồm mọi peer_id đã có ít nhất 1 tin nhắn trong `chat_histories` (kể cả khi đã offline),
          cộng với peer đang mở chat (`_active_peer_id`) hoặc đang xem lịch sử (`_viewing_offline_peer_id`).
        - Sắp xếp theo thời gian tin nhắn gần nhất giảm dần (mới nhất lên trên cùng).
        """
        candidate_ids: Set[str] = set()
        histories_snapshot = dict(self.shared_state.chat_histories)
        for pid, msgs in histories_snapshot.items():
            visible = [m for m in msgs if isinstance(m, ChatMessage) and not m.is_system and id(m) not in self._deleted_for_me_ids]
            if visible:
                candidate_ids.add(pid)
        if self._active_peer_id:
            candidate_ids.add(self._active_peer_id)
        if self._viewing_offline_peer_id:
            candidate_ids.add(self._viewing_offline_peer_id)

        entries: List[Tuple[PeerInfo, Optional[ChatMessage], float]] = []
        for pid in candidate_ids:
            raw_msgs = histories_snapshot.get(pid, [])
            visible = [m for m in raw_msgs if isinstance(m, ChatMessage) and not m.is_system and id(m) not in self._deleted_for_me_ids]
            last_msg = visible[-1] if visible else None
            sort_ts = last_msg.timestamp if last_msg is not None else time.time()
            peer = online_by_id.get(pid)
            if peer is None:
                peer = self._build_offline_peer_info(pid, visible)
            entries.append((peer, last_msg, sort_ts))

        entries.sort(key=lambda item: (-item[2], item[0].name.lower(), item[0].peer_id))
        return entries

    def _add_empty_sidebar_item(self, message: str) -> None:
        item = QListWidgetItem()
        item.setFlags(Qt.NoItemFlags)
        item.setData(Qt.UserRole, None)
        lbl = QLabel(message)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {PLACEHOLDER_COLOR}; font-size: 12px; padding: 24px 12px;")
        item.setSizeHint(QSize(0, max(84, lbl.sizeHint().height())))
        self.peer_list_widget.addItem(item)
        self.peer_list_widget.setItemWidget(item, lbl)

    @Slot()
    def on_peer_list_updated(self) -> None:
        all_peers = self.shared_state.get_online_peers()
        online_by_id: Dict[str, PeerInfo] = {}
        for p in all_peers:
            self._peer_names[p.peer_id] = p.name
            self._known_peers[p.peer_id] = p
            online_by_id[p.peer_id] = p

        # Tab Online Users chỉ lọc những bạn bè đang có trạng thái status == "online" (ẩn away & offline),
        # đồng thời giữ nguyên chỉ số 1-based khớp với lệnh `/list` và `/chat <number>`.
        strict_online: List[Tuple[int, PeerInfo]] = [
            (index, peer) for index, peer in enumerate(all_peers, start=1) if peer.status == "online"
        ]
        chat_entries = self._collect_all_chat_entries(online_by_id)

        scroll_value = self.peer_list_widget.verticalScrollBar().value()
        self.peer_list_widget.setUpdatesEnabled(False)
        self.peer_list_widget.clear()

        selected_peer_id = self._active_peer_id or self._viewing_offline_peer_id
        added_count = 0

        if self._sidebar_tab == "all_chats":
            for idx, (peer, last_msg, _sort_ts) in enumerate(chat_entries, start=1):
                preview = self._format_last_message_preview(last_msg)
                if self._search_filter_text:
                    haystack = f"{peer.name} {peer.ip}:{peer.tcp_port} {peer.status} {preview}".lower()
                    if self._search_filter_text not in haystack:
                        continue

                is_active = peer.peer_id == selected_peer_id
                unread = 0 if is_active else self.shared_state.get_unread_count(peer.peer_id)

                item = QListWidgetItem()
                item.setData(Qt.UserRole, peer.peer_id)
                item.setToolTip(
                    f"{peer.name}\n{peer.ip}:{peer.tcp_port}\nStatus: {peer.status}"
                    + (f"\nUnread: {unread}" if unread else "")
                )
                row_widget = PeerItemWidget(
                    idx,
                    peer,
                    unread,
                    is_active,
                    mode="chat",
                    last_message_preview=preview,
                    last_message_time=last_msg.timestamp if last_msg is not None else None,
                )
                item.setSizeHint(QSize(0, max(62, row_widget.sizeHint().height())))
                self.peer_list_widget.addItem(item)
                self.peer_list_widget.setItemWidget(item, row_widget)
                item.setSelected(is_active)
                added_count += 1

            if added_count == 0:
                if self._search_filter_text:
                    self._add_empty_sidebar_item("No matching conversations.")
                else:
                    self._add_empty_sidebar_item(
                        "No conversations yet.\nSwitch to Online Users to start chatting."
                    )
        else:
            for index, peer in strict_online:
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
                row_widget = PeerItemWidget(index, peer, unread, is_active, mode="online")
                item.setSizeHint(QSize(0, max(62, row_widget.sizeHint().height())))
                self.peer_list_widget.addItem(item)
                self.peer_list_widget.setItemWidget(item, row_widget)
                item.setSelected(is_active)
                added_count += 1

            if added_count == 0 and self._search_filter_text:
                self._add_empty_sidebar_item("No matching online users.")

        self.peer_list_widget.setUpdatesEnabled(True)
        self.peer_list_widget.verticalScrollBar().setValue(scroll_value)

        self.all_chats_btn.setText(f"All Chats ({len(chat_entries)})")
        self.online_users_btn.setText(f"Online Users ({len(strict_online)})")
        self._refresh_chat_header(all_peers)

    @Slot(str)
    def on_system_notification(self, text: str) -> None:
        if not text:
            return
        stripped = text.lstrip()
        is_error = stripped.startswith("[!]")
        color = ERROR_COLOR if is_error else SYSTEM_COLOR

        # Luôn ghi nhận vào QTextEdit ẩn (`self.chat_display`) để giữ tương thích cho bộ kiểm thử tự động
        self._append_html(
            f'<span style="color:{color};">{self._escape_multiline(text)}</span>',
            monospace=True,
        )

        # Trên giao diện khung chat thật (`self.chat_canvas`), ẩn toàn bộ thông báo hệ thống [*]
        # trong lúc chat (gửi/nhận file, thu hồi, bắt đầu chat, online/offline...);
        # chỉ hiển thị lỗi [!] hoặc kết quả khi người dùng chủ động gõ lệnh /list hay /help.
        show_on_canvas = is_error or stripped.startswith(
            (
                "[*] Available commands:",
                "[*] Online users",
                "[*] No other users online",
            )
        )
        if not show_on_canvas:
            return

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

    @Slot(str, object)
    def on_chat_message_received(self, peer_id: str, message: object) -> None:
        if isinstance(message, ChatMessage) and message.content.startswith(REACT_PREFIX):
            payload_part = message.content[len(REACT_PREFIX):]
            history_list = self.shared_state.chat_histories.get(peer_id, [])
            if message in history_list:
                history_list.remove(message)
            if "|" in payload_part:
                target_key, emoji_val = payload_part.rsplit("|", 1)
                for candidate in reversed(history_list):
                    if not candidate.is_recalled and (
                        candidate.msg_id == target_key or candidate.content == target_key
                    ):
                        if emoji_val:
                            candidate.reactions[peer_id] = emoji_val
                        else:
                            candidate.reactions.pop(peer_id, None)
                        widget = self._bubble_widgets.get(id(candidate))
                        if widget is not None:
                            widget.refresh_appearance()
                        break
            return

        if isinstance(message, ChatMessage) and message.content.startswith(REPLY_PREFIX):
            payload_part = message.content[len(REPLY_PREFIX):]
            if "|" in payload_part:
                reply_quote, real_body = payload_part.split("|", 1)
                message.reply_to_text = reply_quote
                message.content = real_body

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
                # Nếu là tin nhắn vừa được đánh dấu thu hồi hoặc thả cảm xúc từ luồng TCP, cập nhật lại bong bóng
                if id(message) in self._bubble_widgets:
                    self._bubble_widgets[id(message)].refresh_appearance()
                    if message.is_recalled:
                        self._rebuild_plain_text_mirror()
                return
            self._rendered_message_ids.add(id(message))
            if isinstance(message, ChatMessage) and id(message) not in self._deleted_for_me_ids:
                self._add_message_bubble(message, animate=True)
            self._append_html(self._format_message(message))
            self._schedule_sidebar_refresh()
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
        self._cancel_reply_bar()
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
                self._add_message_bubble(message, animate=False)
            self._append_html(self._format_message(message))
        self._animate_fade_in(self.chat_canvas, duration_ms=180)

    @Slot(str)
    def on_my_status_changed(self, status: str) -> None:
        self._set_combo_status(status)
        self._refresh_my_avatar()
        self._update_window_title()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._progress_hide_timer.stop()
        self._sidebar_refresh_timer.stop()
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

    def _add_message_bubble(self, message: ChatMessage, animate: bool = False) -> None:
        if message.is_system:
            self.on_system_notification(message.content)
            return
        is_self = message.sender_id == SELF_SENDER_ID
        bubble = ChatBubbleWidget(
            message=message,
            is_self=is_self,
            on_delete_for_me=self._delete_message_for_me,
            on_recall_message=self._recall_message_for_everyone,
            on_react_message=self._react_to_message,
            on_reply_message=self._start_reply_to_message,
            on_forward_message=self._open_forward_dialog,
            parent=self.chat_canvas,
        )
        self._bubble_widgets[id(message)] = bubble
        self._add_chat_widget(bubble)
        if animate:
            self._animate_fade_in(bubble, duration_ms=170)

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
        target_id = self._active_peer_id or self._viewing_offline_peer_id
        if target_id is None:
            return
        self.chat_display.clear()
        for msg in self.shared_state.chat_histories.get(target_id, []):
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
        self._viewing_offline_peer_id = None
        if peer is not None:
            self._peer_names[peer.peer_id] = peer.name
            self._known_peers[peer.peer_id] = peer
        self.leave_btn.setEnabled(peer is not None)
        self.send_file_btn.setEnabled(peer is not None)
        self.message_input.setPlaceholderText(
            "Write a message and press Enter... (or /list, /chat, /send, /status, /leave, /help, /quit)"
        )
        self._refresh_chat_header()
        self._update_window_title()

    def _refresh_chat_header(self, peers: Optional[List[PeerInfo]] = None) -> None:
        if peers is None:
            peers = self.shared_state.get_online_peers()

        if self._active_peer_id is None and self._viewing_offline_peer_id is not None:
            pid = self._viewing_offline_peer_id
            peer = next((p for p in peers if p.peer_id == pid), None)
            name = self._peer_display_name(pid)
            self.chat_header_label.setText(f"Chat history with {name}")
            if peer is None:
                self.channel_tag_label.setText(f"# {name} (Offline)")
                self.chat_sub_label.setText(
                    f'{pid} \u00b7 <span style="color:{OFFLINE_COLOR}">\u25cf</span> Offline (read-only history)'
                )
                self.chat_avatar_label.setPixmap(_build_avatar_pixmap(name, size=46, status="offline"))
            else:
                self.channel_tag_label.setText(f"# {name}")
                self.chat_sub_label.setText(
                    f'{peer.ip}:{peer.tcp_port} \u00b7 <span style="color:{STATUS_COLORS.get(peer.status, OFFLINE_COLOR)}">'
                    f"\u25cf</span> {peer.status} \u00b7 Click user on sidebar to resume chatting"
                )
                self.chat_avatar_label.setPixmap(_build_avatar_pixmap(peer.name, size=46, status=peer.status))
            return

        if self._active_peer_id is None:
            self.chat_header_label.setText("No active chat")
            self.chat_sub_label.setText("Click a user on the left, or type /chat <name|number>")
            self.chat_avatar_label.setPixmap(_build_avatar_pixmap("LAN", size=46, status=None, avatar_index=1))
            self.channel_tag_label.setText("# General")
            return
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
        elif self._viewing_offline_peer_id is not None:
            title += f" - history with {self._peer_display_name(self._viewing_offline_peer_id)} (offline)"
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
