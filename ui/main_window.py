"""
[THÀNH VIÊN C] - Giao diện người dùng chính bằng PySide6 (Thread 1 - Main Thread).
Giải quyết triệt để bài toán "Typing while messages arrive":
- Khung hiển thị lịch sử chat (QTextEdit read-only) và ô nhập văn bản (QLineEdit) tách biệt hoàn toàn.
- Mọi dữ liệu từ các luồng UDP/TCP đi qua AppSignals (QueuedConnection) nên không bao giờ làm vỡ chữ đang gõ.
"""

from PySide6.QtCore import Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from core.shared_state import SharedState
from ui.command_parser import CommandParser
from ui.qt_signals import AppSignals


class MainWindow(QMainWindow):
    """
    Cửa sổ chính của ứng dụng LAN Chat & File Sharing (PySide6).
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
        self.chat_display: QTextEdit
        self.file_progress_bar: QProgressBar
        self.message_input: QLineEdit
        self.send_btn: QPushButton
        self.send_file_btn: QPushButton
        self.leave_btn: QPushButton

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """
        Khởi tạo bố cục (Layout) cơ bản cho cửa sổ PySide6:
        - Cột trái (Sidebar): Thông tin bản thân, hộp chọn trạng thái (online/away), danh sách Online Peers.
        - Cột phải (Main Chat Area): Tiêu đề người đang chat, vùng lịch sử tin nhắn, thanh tiến độ truyền file,
          và thanh nhập lệnh/tin nhắn ở dưới cùng.
        TODO [Thành viên C]: Tinh chỉnh giao diện, màu sắc, stylesheet và các nút chức năng.
        """
        my_name, my_port, my_status = self.shared_state.get_my_info()
        self.setWindowTitle(f"LAN Chat & File Sharing - {my_name} (TCP:{my_port})")
        self.resize(900, 600)

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        splitter = QSplitter(self)
        main_layout.addWidget(splitter)

        # --- Cột trái: Danh sách Peers & Trạng thái ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel(f"User: {my_name} (Port: {my_port})"))

        self.status_combo = QComboBox()
        self.status_combo.addItems(["online", "away"])
        self.status_combo.setCurrentText(my_status)
        left_layout.addWidget(self.status_combo)

        left_layout.addWidget(QLabel("Online Peers:"))
        self.peer_list_widget = QListWidget()
        left_layout.addWidget(self.peer_list_widget)
        splitter.addWidget(left_panel)

        # --- Cột phải: Khung Chat, Thanh Progress & Ô nhập liệu ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        header_layout = QHBoxLayout()
        self.chat_header_label = QLabel("Chưa chọn người chat (Gõ /help hoặc click vào Peer bên trái)")
        self.leave_btn = QPushButton("Leave (/leave)")
        header_layout.addWidget(self.chat_header_label)
        header_layout.addWidget(self.leave_btn)
        right_layout.addLayout(header_layout)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        right_layout.addWidget(self.chat_display)

        self.file_progress_bar = QProgressBar()
        self.file_progress_bar.setValue(0)
        self.file_progress_bar.setVisible(False)
        right_layout.addWidget(self.file_progress_bar)

        input_layout = QHBoxLayout()
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Nhập tin nhắn hoặc lệnh (/list, /chat, /send, /status, /leave, /help, /quit)...")
        self.send_btn = QPushButton("Send")
        self.send_file_btn = QPushButton("Send File...")
        input_layout.addWidget(self.message_input)
        input_layout.addWidget(self.send_btn)
        input_layout.addWidget(self.send_file_btn)
        right_layout.addLayout(input_layout)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

    def _connect_signals(self) -> None:
        """
        Kết nối các sự kiện nút bấm trên GUI và các tín hiệu từ `self.signals` (AppSignals) vào các Slot xử lý.
        TODO [Thành viên C]: Kết nối thêm sự kiện click đúp vào peer_list_widget, QFileDialog cho nút Send File, v.v.
        """
        self.signals.peer_list_updated.connect(self.on_peer_list_updated)
        self.signals.system_notification.connect(self.on_system_notification)
        self.signals.chat_message_received.connect(self.on_chat_message_received)
        self.signals.file_progress_updated.connect(self.on_file_progress_updated)
        self.signals.peer_disconnected.connect(self.on_peer_disconnected)

        self.message_input.returnPressed.connect(self._on_submit_input)
        self.send_btn.clicked.connect(self._on_submit_input)

    @Slot()
    def _on_submit_input(self) -> None:
        """
        Lấy chuỗi từ `self.message_input`, xóa trống ô nhập và chuyển cho `self.command_parser.handle_user_input()`.
        TODO [Thành viên C]: Hoàn thiện xử lý khi người dùng nhấn Enter hoặc nút Send.
        """
        pass

    @Slot()
    def on_peer_list_updated(self) -> None:
        """
        Slot cập nhật lại danh sách người dùng trên Sidebar kèm trạng thái (online/away) và số tin chưa đọc (unread).
        TODO [Thành viên C]: Đọc `self.shared_state.get_online_peers()` và vẽ lại `self.peer_list_widget`.
        """
        pass

    @Slot(str)
    def on_system_notification(self, text: str) -> None:
        """
        Slot hiển thị dòng thông báo hệ thống (VD: `[*] New message from Huy (1 unread)`) lên `self.chat_display`.
        TODO [Thành viên C]: Append thông báo hệ thống vào khung chat mà không làm mất chữ đang gõ ở `message_input`.
        """
        pass

    @Slot(str, object)
    def on_chat_message_received(self, peer_id: str, message: object) -> None:
        """
        Slot xử lý khi có tin nhắn mới đến:
        - Nếu `peer_id` đang là `active_chat`: Hiển thị ngay nội dung tin nhắn lên `self.chat_display`.
        - Nếu `peer_id` KHÔNG phải `active_chat`: Cập nhật badge số lượng unread trên Sidebar và in thông báo.
        TODO [Thành viên C]: Hiện thực logic hiển thị tin nhắn theo ngữ cảnh cuộc trò chuyện.
        """
        pass

    @Slot(str, str, int)
    def on_file_progress_updated(self, peer_id: str, filename: str, percentage: int) -> None:
        """
        Slot cập nhật thanh tiến độ `self.file_progress_bar` khi đang gửi hoặc nhận file.
        TODO [Thành viên C]: Hiện thanh progress bar, cập nhật giá trị % và ẩn đi khi đạt 100%.
        """
        pass

    @Slot(str, str)
    def on_peer_disconnected(self, peer_id: str, reason: str) -> None:
        """
        Slot xử lý khi peer ngắt kết nối đột ngột hoặc gửi `BYE|`.
        TODO [Thành viên C]: Thông báo cho người dùng và cập nhật lại trạng thái khung chat nếu đang chat với peer đó.
        """
        pass

    def closeEvent(self, event: QCloseEvent) -> None:
        """
        Bắt sự kiện đóng cửa sổ (nút X) để dọn dẹp các luồng UDP/TCP tương tự lệnh `/quit`.
        TODO [Thành viên C]: Gọi xử lý thoát an toàn trước khi `event.accept()`.
        """
        super().closeEvent(event)
