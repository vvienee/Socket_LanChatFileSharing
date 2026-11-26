"""
Script kiểm thử độc lập dành cho [THÀNH VIÊN B].
Dùng để test đóng/mở khung giao thức (`network/protocol.py`), `TCPConnectionManager` và `FileTransferService`
mà không cần chờ UDP của A hay GUI của C.
Cách chạy:
    python -m tests.mock_b_protocol
"""

import os
import shutil
import socket
import tempfile
import threading
import time
from typing import List, Tuple
from core.models import PeerInfo
from core.shared_state import SharedState
from network.protocol import (
    FRAME_BYE,
    FRAME_FILE,
    FRAME_MSG,
    encode_bye,
    encode_file_header,
    encode_hello,
    encode_msg,
    decode_hello,
    read_frame_header,
    recv_exact,
)
from network.tcp_manager import TCPConnectionManager


class DummySignal:
    """Giả lập Qt Signal cho môi trường chạy test trên Terminal."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.events: List[Tuple] = []

    def emit(self, *args) -> None:
        self.events.append(args)
        if self.name in ("system_notification", "peer_disconnected"):
            print(f"  [Signal:{self.name}] {args}")


class DummyAppSignals:
    """Giả lập AppSignals của Thành viên C."""

    def __init__(self) -> None:
        self.peer_list_updated = DummySignal("peer_list_updated")
        self.system_notification = DummySignal("system_notification")
        self.chat_message_received = DummySignal("chat_message_received")
        self.file_progress_updated = DummySignal("file_progress_updated")
        self.peer_disconnected = DummySignal("peer_disconnected")


def test_1_protocol_framing() -> None:
    print("\n=== TEST 01: Kiểm tra Framing & UTF-8 Tiếng Việt (Chống dính gói) ===")

    # Kiểm tra HELLO.
    hello_bytes = encode_hello("Nguyễn Hoàng Quân", 5001, "online")
    assert decode_hello(hello_bytes) == ("Nguyễn Hoàng Quân", 5001, "online")

    # Tạo cặp socket kết nối trực tiếp trong bộ nhớ (socketpair).
    s_send, s_recv = socket.socketpair()
    try:
        vietnamese_msg = "Xin chào Minh! Đã kiểm tra slide chưa? 🚀 Tiếng Việt có dấu 100%."

        # Bắn dính liền 03 khung tin vào cùng 01 luồng byte TCP.
        stream_data = (
            encode_msg(vietnamese_msg)
            + encode_file_header("báo_cáo|cuối_kỳ.txt", 5)
            + b"12345"
            + encode_bye()
        )
        s_send.sendall(stream_data)

        # 1. Đọc MSG.
        ftype, args = read_frame_header(s_recv)
        assert ftype == FRAME_MSG
        body = recv_exact(s_recv, int(args[0])).decode("utf-8")
        assert body == vietnamese_msg

        # 2. Đọc FILE.
        ftype, args = read_frame_header(s_recv)
        assert ftype == FRAME_FILE
        assert args == ["báo_cáo_cuối_kỳ.txt", "5"]
        file_bytes = recv_exact(s_recv, int(args[1]))
        assert file_bytes == b"12345"

        # 3. Đọc BYE.
        ftype, args = read_frame_header(s_recv)
        assert ftype == FRAME_BYE and args == []

        print("==> PASSED: Bóc tách chính xác MSG (UTF-8), FILE và BYE từ luồng byte dính liền.")
    finally:
        s_send.close()
        s_recv.close()


def test_2_concurrent_chat_and_file() -> None:
    print("\n=== TEST 02: Truyền 50 tin nhắn + Gửi file 01 MB đồng thời giữa 02 TCPManager ===")

    temp_dir = tempfile.mkdtemp(prefix = "lanchat_test_")
    recv_download_dir = os.path.join(temp_dir, "downloads")
    sample_file = os.path.join(temp_dir, "slides_demo.bin")

    # Tạo file mẫu 01 MB có nội dung xác định.
    original_content = os.urandom(1024 * 1024)
    with open(sample_file, "wb") as f:
        f.write(original_content)

    state_quan = SharedState(my_name = "Quan", my_tcp_port = 16001)
    state_minh = SharedState(my_name = "Minh", my_tcp_port = 16002)

    # Đăng ký thông tin peer chéo nhau (giả lập kết quả từ UDP Discovery của A).
    state_quan.upsert_peer("Minh", "127.0.0.1", 16002, "online")
    state_minh.upsert_peer("Quan", "127.0.0.1", 16001, "online")

    sig_quan = DummyAppSignals()
    sig_minh = DummyAppSignals()

    mgr_quan = TCPConnectionManager(state_quan, sig_quan, listen_port = 16001, download_dir = temp_dir)
    mgr_minh = TCPConnectionManager(state_minh, sig_minh, listen_port = 16002, download_dir = recv_download_dir)

    try:
        mgr_quan.start_server()
        mgr_minh.start_server()
        time.sleep(0.2)

        peer_minh = PeerInfo(name = "Minh", ip = "127.0.0.1", tcp_port = 16002, status = "online")
        assert mgr_quan.connect_to_peer(peer_minh), "Không thể kết nối tới Minh"
        time.sleep(0.1)

        # Bắt đầu gửi file 01 MB bất đồng bộ (Thread 06).
        mgr_quan.send_file_async("127.0.0.1:16002", sample_file)

        # Trong lúc file đang truyền, bắn liên tục 50 tin nhắn chat.
        for i in range(1, 51):
            assert mgr_quan.send_text_message("127.0.0.1:16002", f"Tin nhắn song song số #{i}")

        # Chờ hoàn tất truyền nhận.
        time.sleep(1.0)

        saved_file = os.path.join(recv_download_dir, "slides_demo.bin")
        assert os.path.isfile(saved_file), "File nhận được không tồn tại!"
        with open(saved_file, "rb") as f:
            received_content = f.read()
        assert received_content == original_content, "Nội dung file bị sai lệch!"
        assert len(sig_minh.chat_message_received.events) == 50, (
            f"Mong đợi 50 tin nhắn nhưng nhận được {len(sig_minh.chat_message_received.events)}"
        )

        print("==> PASSED: Nhận đủ 50/50 tin nhắn và toàn vẹn 100% file 01 MB khi chạy song song !")
    finally:
        mgr_quan.stop_all()
        mgr_minh.stop_all()
        shutil.rmtree(temp_dir, ignore_errors = True)


def test_3_interrupted_file_cleanup() -> None:
    print("\n=== TEST 03: Giả lập đứt kết nối giữa chừng --> Tự động xóa file lỗi ===")
    temp_dir = tempfile.mkdtemp(prefix = "lanchat_abort_")
    recv_download_dir = os.path.join(temp_dir, "downloads")

    state_minh = SharedState(my_name = "Minh", my_tcp_port = 16004)
    sig_minh = DummyAppSignals()
    mgr_minh = TCPConnectionManager(state_minh, sig_minh, listen_port = 16004, download_dir = recv_download_dir)

    try:
        mgr_minh.start_server()
        time.sleep(0.2)

        # Tạo socket thô đóng giả người gửi: khai báo file 5MB nhưng chỉ gửi 100KB rồi cắt kết nối.
        rogue_sender = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        rogue_sender.connect(("127.0.0.1", 16004))
        rogue_sender.sendall(encode_file_header("corrupted_video.mp4", 5 * 1024 * 1024))
        rogue_sender.sendall(b"X" * (100 * 1024))
        time.sleep(0.2)
        rogue_sender.close()  # Ngắt ngang kết nối.
        time.sleep(0.5)
        leaked_file = os.path.join(recv_download_dir, "corrupted_video.mp4")
        assert not os.path.exists(leaked_file), "File lỗi chưa được xóa!"
        print("==> PASSED: File dở dang (corrupted_video.mp4) đã được tự động xóa sạch!")
    finally:
        mgr_minh.stop_all()
        shutil.rmtree(temp_dir, ignore_errors = True)


def main() -> None:
    test_1_protocol_framing()
    test_2_concurrent_chat_and_file()
    test_3_interrupted_file_cleanup()
    print("\n[OK] Toàn bộ kịch bản kiểm thử của Thành viên B đã vượt qua !!!")


if __name__ == "__main__":
    main()