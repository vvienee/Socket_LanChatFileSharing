"""
[THÀNH VIÊN C] - Định nghĩa các Qt Signals đóng vai trò hợp đồng giao tiếp (Thread-safe Bridge)
giữa các luồng chạy ngầm (UDP Broadcaster/Listener, TCP Acceptor/Receiver, File Sender)
và luồng giao diện chính (Main GUI Thread của PySide6).

Nguyên lý an toàn luồng:
- `AppSignals` được tạo ở Main Thread nên "thuộc về" Main Thread.
- Các Slot của `MainWindow` cũng sống ở Main Thread.
- Khi một luồng nền (Thread 2..6) gọi `signal.emit(...)`, Qt phát hiện luồng phát khác luồng nhận
  và tự động dùng `Qt.QueuedConnection`: tham số được đóng gói vào hàng đợi sự kiện của Main Thread,
  Slot chỉ chạy khi vòng lặp sự kiện Qt rảnh -> không bao giờ có 2 luồng cùng vẽ lên widget.
"""

from PySide6.QtCore import QObject, Signal


class AppSignals(QObject):
    """
    Tập hợp các tín hiệu sự kiện toàn cục của ứng dụng.
    Thành viên A và B chỉ cần gọi `signals.<ten_signal>.emit(...)` từ bất kỳ luồng nào,
    Qt sẽ tự động đẩy sự kiện về Main Thread của Thành viên C một cách an toàn.
    """

    # ------------------------------------------------------------------
    # Hợp đồng gốc (overview.md mục 4.3) - Thành viên A/B phát từ luồng nền
    # ------------------------------------------------------------------

    # Phát ra khi danh sách peers hoặc số lượng tin nhắn chưa đọc (unread_count) thay đổi
    peer_list_updated = Signal()

    # Phát ra khi có thông báo hệ thống cần in lên màn hình (VD: "[*] Minh is now online")
    system_notification = Signal(str)

    # Phát ra khi có một tin nhắn mới trong lịch sử của peer_id: (peer_id: str, message: ChatMessage)
    # - Thành viên B phát khi nhận được khung MSG từ peer.
    # - CommandParser (C) cũng phát với message.sender_id == "SELF" sau khi tự gửi thành công,
    #   để GUI hiển thị tin nhắn của chính mình theo cùng một đường đi.
    chat_message_received = Signal(str, object)

    # Phát ra khi tiến độ gửi/nhận file thay đổi: (peer_id: str, filename: str, percentage: int)
    # Quy ước bổ sung: percentage < 0 nghĩa là lượt truyền bị lỗi/hủy (GUI sẽ ẩn thanh tiến độ).
    file_progress_updated = Signal(str, str, int)

    # Phát ra khi một peer ngắt kết nối TCP hoặc gửi BYE|: (peer_id: str, reason: str)
    peer_disconnected = Signal(str, str)

    # ------------------------------------------------------------------
    # Tín hiệu nội bộ của phân hệ C (chỉ CommandParser phát, từ Main Thread)
    # ------------------------------------------------------------------

    # Phát ra khi đổi cuộc trò chuyện hiện tại (/chat hoặc /leave):
    # (peer: PeerInfo | None, history: List[ChatMessage], unread_before_switch: int)
    active_chat_changed = Signal(object, object, int)

    # Phát ra khi trạng thái của bản thân đổi bằng lệnh /status: (new_status: str)
    # Giúp ComboBox trên Sidebar luôn đồng bộ khi người dùng gõ lệnh thay vì click.
    my_status_changed = Signal(str)
