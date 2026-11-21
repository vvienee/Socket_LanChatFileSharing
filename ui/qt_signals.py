"""
[THÀNH VIÊN C] - Định nghĩa các Qt Signals đóng vai trò hợp đồng giao tiếp (Thread-safe Bridge)
giữa các luồng chạy ngầm (UDP Broadcaster/Listener, TCP Acceptor/Receiver, File Sender)
và luồng giao diện chính (Main GUI Thread của PySide6).
"""

from PySide6.QtCore import QObject, Signal


class AppSignals(QObject):
    """
    Tập hợp các tín hiệu sự kiện toàn cục của ứng dụng.
    Thành viên A và B chỉ cần gọi `signals.<ten_signal>.emit(...)` từ bất kỳ luồng nào,
    Qt sẽ tự động đẩy sự kiện về Main Thread của Thành viên C một cách an toàn.
    """

    # Phát ra khi danh sách peers hoặc số lượng tin nhắn chưa đọc (unread_count) thay đổi
    peer_list_updated = Signal()

    # Phát ra khi có thông báo hệ thống cần in lên màn hình (VD: "[*] Minh is now online")
    system_notification = Signal(str)

    # Phát ra khi nhận được một tin nhắn mới: (peer_id: str, message: ChatMessage)
    chat_message_received = Signal(str, object)

    # Phát ra khi tiến độ gửi/nhận file thay đổi: (peer_id: str, filename: str, percentage: int)
    file_progress_updated = Signal(str, str, int)

    # Phát ra khi một peer ngắt kết nối TCP hoặc gửi BYE|: (peer_id: str, reason: str)
    peer_disconnected = Signal(str, str)
