"""
[THÀNH VIÊN B] - Định nghĩa giao thức tầng ứng dụng (Application-Layer Protocol) và Message Framing.
Theo đặc tả trong plan.md:
- UDP Presence: HELLO|<name>|<tcp_port>|<status>
- TCP Chat Message: MSG|<length_in_bytes>|<utf-8 text>
- TCP File Transfer: FILE|<filename>|<size_in_bytes>|<raw file bytes>
- TCP Disconnect: BYE|
"""

import socket
from typing import List, Optional, Tuple

# Các hằng số loại gói tin (Frame Types)
FRAME_HELLO = "HELLO"
FRAME_MSG = "MSG"
FRAME_FILE = "FILE"
FRAME_BYE = "BYE"
DELIMITER = "|"
ENCODING = "utf-8"


def encode_hello(name: str, tcp_port: int, status: str) -> bytes:
    """
    Đóng gói bản tin UDP Presence: 'HELLO|<name>|<tcp_port>|<status>'.
    TODO [Thành viên B / A]: Trả về chuỗi bytes đã mã hóa UTF-8.
    """
    pass


def decode_hello(data: bytes) -> Optional[Tuple[str, int, str]]:
    """
    Giải mã bản tin UDP Presence.
    Trả về (name, tcp_port, status) nếu hợp lệ, ngược lại trả về None.
    TODO [Thành viên B / A]: Kiểm tra tiền tố 'HELLO|' và ép kiểu tcp_port sang int an toàn.
    """
    return None


def encode_msg(text: str) -> bytes:
    """
    Đóng gói tin nhắn văn bản gửi qua TCP: 'MSG|<byte_length>|<utf-8 text>'.
    Lưu ý: <byte_length> là số byte sau khi encode UTF-8 (không phải len(str) vì tiếng Việt có dấu tốn nhiều hơn 1 byte).
    TODO [Thành viên B]: Mã hóa chuỗi sang utf-8, tính len(payload) và ghép header.
    """
    pass


def encode_file_header(filename: str, filesize: int) -> bytes:
    """
    Đóng gói phần Header trước khi truyền luồng byte của file: 'FILE|<filename>|<size_in_bytes>|'.
    Lưu ý: Chỉ lấy basename của filename (tránh lộ đường dẫn tuyệt đối trên máy gửi).
    TODO [Thành viên B]: Tạo header chuẩn bị cho việc gửi raw bytes.
    """
    pass


def encode_bye() -> bytes:
    """
    Đóng gói tín hiệu ngắt kết nối lịch sự: 'BYE|'.
    TODO [Thành viên B]: Trả về b"BYE|".
    """
    return b"BYE|"


def recv_exact(sock: socket.socket, num_bytes: int) -> bytes:
    """
    Đọc chính xác `num_bytes` từ TCP socket (lặp qua sock.recv() cho tới khi nhận đủ byte).
    Nếu kết nối bị đóng trước khi đọc đủ (recv trả về b''), ném ngoại lệ ConnectionError.
    TODO [Thành viên B]: Hiện thực vòng lặp đọc đủ số byte để chống phân mảnh gói tin TCP.
    """
    pass


def read_frame_header(sock: socket.socket) -> Tuple[str, List[str]]:
    """
    Đọc từng phần header phân tách bởi ký tự '|' từ dòng TCP cho đến khi xác định được loại khung tin:
    - Nếu là 'BYE': Đọc tới dấu '|' đầu tiên -> trả về ('BYE', []).
    - Nếu là 'MSG': Đọc tiếp phần <length>| -> trả về ('MSG', [length_str]).
    - Nếu là 'FILE': Đọc tiếp <filename>|<size>| -> trả về ('FILE', [filename, size_str]).
    TODO [Thành viên B]: Hiện thực hàm đọc header an toàn trên byte stream.
    """
    pass
