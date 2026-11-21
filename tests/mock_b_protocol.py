"""
Script kiểm thử độc lập dành cho [THÀNH VIÊN B].
Dùng để test đóng/mở khung giao thức (`network/protocol.py`), `TCPConnectionManager` và `FileTransferService`
mà không cần chờ UDP của A hay GUI của C.
Cách chạy:
    python -m tests.mock_b_protocol
"""


def main() -> None:
    """
    TODO [Thành viên B]:
    Viết các kịch bản kiểm thử cho tầng TCP & Framing:
    1. Kiểm tra `encode_msg`, `encode_file_header`, `encode_bye` và `read_frame_header` + `recv_exact`
       với chuỗi tiếng Việt có dấu (UTF-8 multi-byte).
    2. Mở 2 instance `TCPConnectionManager` trên cổng 6001 và 6002, gửi 50 tin nhắn liên tiếp
       đồng thời truyền 1 file vào `downloads/` để xác nhận không bị dính gói (sticky packets).
    3. Giả lập ngắt socket giữa lúc đang truyền file để kiểm tra file dở dang có bị xóa sạch không.
    """
    print("[Mock Test B] Skeleton sẵn sàng. Thành viên B viết kịch bản test TCP Framing & File Transfer tại đây.")


if __name__ == "__main__":
    main()
