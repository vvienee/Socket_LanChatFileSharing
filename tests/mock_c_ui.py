"""
Script kiểm thử độc lập dành cho [THÀNH VIÊN C].
Dùng để bật giao diện PySide6 với dữ liệu Peer giả lập (Mock Peers) và dùng QTimer
bắn tin nhắn tự động mỗi 1 giây nhằm kiểm chứng:
- Khi đang gõ dở câu dài trong ô Input, tin nhắn từ người khác đổ về không làm vỡ chữ hay mất con trỏ.
- Các lệnh /list, /chat, /status, /leave, /help, /quit hoạt động đúng.
Cách chạy:
    python -m tests.mock_c_ui
"""


def main() -> None:
    """
    TODO [Thành viên C]:
    Khởi tạo QApplication, nạp vài PeerInfo giả vào SharedState và dùng QTimer phát
    `signals.chat_message_received.emit(...)` định kỳ để test giao diện PySide6 độc lập.
    """
    print("[Mock Test C] Skeleton sẵn sàng. Thành viên C viết kịch bản test giao diện PySide6 tại đây.")


if __name__ == "__main__":
    main()
