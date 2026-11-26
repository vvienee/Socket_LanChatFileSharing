"""
[THÀNH VIÊN B] - Định nghĩa giao thức tầng ứng dụng (Application-Layer Protocol) và Message Framing.
Theo đặc tả trong plan.md:
- UDP Presence: HELLO|<name>|<tcp_port>|<status>
- TCP Chat Message: MSG|<length_in_bytes>|<utf-8 text>
- TCP File Transfer: FILE|<filename>|<size_in_bytes>|<raw file bytes>
- TCP Disconnect: BYE|
"""

import os
import socket
from typing import List, Optional, Tuple

# Các hằng số loại gói tin (Frame Types).
FRAME_HELLO = "HELLO"
FRAME_MSG = "MSG"
FRAME_FILE = "FILE"
FRAME_BYE = "BYE"
DELIMITER = "|"
ENCODING = "utf-8"

# Giới hạn an toàn để tránh tràn bộ nhớ nếu nhận phải dữ liệu rác không có dấu '|'.
MAX_HEADER_FIELD_BYTES = 4096


def encode_hello(name: str, tcp_port: int, status: str) -> bytes:
    """
    Đóng gói bản tin UDP Presence: "HELLO|<name>|<tcp_port>|<status>".
    """

    safe_name = name.replace(DELIMITER, "_") # replace: "|" --> "_"
    payload = f"{FRAME_HELLO}{DELIMITER}{safe_name}{DELIMITER}{tcp_port}{DELIMITER}{status}"
    return payload.encode(ENCODING)


def encode_tcp_hello(name: str, tcp_port: int, status: str) -> bytes:
    """
    Đóng gói khung định danh Peer gửi ngay khi mở kết nối TCP:
    "HELLO|<name>|<tcp_port>|<status>|".
    Giúp bên nhận biết chính xác cổng TCP lắng nghe của bên gửi (đặc biệt khi chạy nhiều peer trên 1 máy).
    """

    safe_name = name.replace(DELIMITER, "_")
    payload = f"{FRAME_HELLO}{DELIMITER}{safe_name}{DELIMITER}{tcp_port}{DELIMITER}{status}{DELIMITER}"
    return payload.encode(ENCODING)


def decode_hello(data: bytes) -> Optional[Tuple[str, int, str]]:
    """
    Giải mã bản tin UDP Presence: trả về (name, tcp_port, status) nếu hợp lệ. Ngược lại, trả về None.
    """

    try:
        # strip(): xóa khoảng trắng, kí tự xuống dòng ở đầu và cuối chuỗi.
        text = data.decode(ENCODING).strip()

        # parts = ["HELLO", "<name>", "<tcp_port>", "<status>"]
        parts = text.split(DELIMITER) # trả về một list các chuỗi, được phân tách bởi "|".

        if len(parts) != 4 or parts[0] != FRAME_HELLO:
            return None

        # Lấy dữ liệu.
        name = parts[1].strip()
        tcp_port = int(parts[2])
        status = parts[3].strip()

        if not name or not (1 <= tcp_port <= 65535) or status not in ("online", "away"):
            return None

        return (name, tcp_port, status)

    except (UnicodeDecodeError, ValueError):
        return None


def encode_msg(text: str) -> bytes:
    """
    Đóng gói tin nhắn văn bản gửi qua TCP: "MSG|<byte_length>|<utf-8 text>".
    """

    body_bytes = text.encode(ENCODING)
    header = f"{FRAME_MSG}{DELIMITER}{len(body_bytes)}{DELIMITER}".encode(ENCODING)
    return header + body_bytes


def encode_file_header(filename: str, filesize: int) -> bytes:
    """
    Đóng gói phần header trước khi truyền luồng byte của file: "FILE|<filename>|<size_in_bytes>|".
    """

    # os.path.basename(filename): lấy tên file gốc, bỏ đường dẫn cha.
    base_name = os.path.basename(filename).replace(DELIMITER, "_") # replace: "|" --> "_"
    header = f"{FRAME_FILE}{DELIMITER}{base_name}{DELIMITER}{filesize}{DELIMITER}"
    return header.encode(ENCODING)


def encode_bye() -> bytes:
    """
    Đóng gói tín hiệu ngắt kết nối lịch sự: "BYE|".
    """

    return f"{FRAME_BYE}{DELIMITER}".encode(ENCODING)


def recv_exact(sock: socket.socket, num_bytes: int) -> bytes:
    """
    Đọc chính xác `num_bytes` từ TCP socket (lặp qua sock.recv() cho tới khi nhận đủ byte).
    Nếu kết nối bị đóng trước khi đọc đủ (recv trả về b''), ném ngoại lệ ConnectionError.
    """

    if num_bytes == 0:
        return b""

    chunks = bytearray()
    remaining = num_bytes
    while remaining > 0:
        # Đọc tối đa 64KB mỗi lần để tối ưu hiệu năng bộ đệm.
        chunk = sock.recv(min(remaining, 65536))

        if not chunk:
            raise ConnectionError(
                f"Kết nối TCP bị đóng bất ngờ (thiếu {remaining}/{num_bytes} bytes)."
            )

        chunks.extend(chunk)
        remaining -= len(chunk)

    return bytes(chunks)


def _read_until_delimiter(sock: socket.socket, delimiter: bytes = b"|") -> str:
    """
    Đọc từng byte từ socket cho tới khi gặp ký tự phân tách "delimiter" (mặc định "|").
    Dùng riêng cho việc đọc các trường header ngắn để không lấn sang phần payload phía sau.
    """

    buffer = bytearray()
    while True:
        # Đọc từng byte từ socket.
        chunk = sock.recv(1)

        if not chunk:
            if len(buffer) == 0:
                raise ConnectionError("Peer đã đóng kết nối.")
            raise ConnectionError("Kết nối bị ngắt giữa chừng khi đang đọc header.")

        if chunk == delimiter:
            return buffer.decode(ENCODING)

        buffer.extend(chunk)

        if len(buffer) > MAX_HEADER_FIELD_BYTES:
            raise ValueError("Trường header vượt quá kích thước cho phép (gói tin sai định dạng).")


def read_frame_header(sock: socket.socket) -> Tuple[str, List[str]]:
    """
    Đọc từng phần header phân tách bởi ký tự "|" từ dòng TCP cho đến khi xác định được loại khung tin:
    - Nếu là "HELLO": đọc tiếp <name>|<tcp_port>|<status>| --> return ("HELLO", [name, port_str, status]).
    - Nếu là "BYE": đọc tới dấu "|" đầu tiên --> return ("BYE", []).
    - Nếu là "MSG": đọc tiếp phần <length>| --> return ("MSG", [length_str]).
    - Nếu là "FILE": đọc tiếp phần <filename>|<size_in_bytes>| --> return ("FILE", [filename, size_str]).
    """

    frame_type = _read_until_delimiter(sock)

    if frame_type == FRAME_HELLO:
        name = _read_until_delimiter(sock).strip()
        port_str = _read_until_delimiter(sock).strip()
        status = _read_until_delimiter(sock).strip()
        if not name or not port_str.isdigit() or not (1 <= int(port_str) <= 65535) or status not in ("online", "away"):
            raise ValueError(f"Khung HELLO trên TCP không hợp lệ: {name!r}, {port_str!r}, {status!r}")
        return (FRAME_HELLO, [name, port_str, status])

    if frame_type == FRAME_BYE:
        return (FRAME_BYE, [])

    if frame_type == FRAME_MSG:
        length_str = _read_until_delimiter(sock)
        if not length_str.isdigit():
            raise ValueError(f"Độ dài MSG không hợp lệ: {length_str!r}")
        return (FRAME_MSG, [length_str])

    if frame_type == FRAME_FILE:
        filename = _read_until_delimiter(sock)
        size_str = _read_until_delimiter(sock)
        if not size_str.isdigit():
            raise ValueError(f"Kích thước FILE không hợp lệ: {size_str!r}")
        return (FRAME_FILE, [filename, size_str])

    raise ValueError(f"Loại khung tin không được hỗ trợ: {frame_type!r}")