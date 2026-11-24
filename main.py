"""
Entry Point chính của ứng dụng LAN Chat & File Sharing (P2P UDP + TCP với giao diện PySide6).
Ví dụ khởi chạy:
    python main.py --name Quan --port 5001
    python main.py --name Minh --port 5002 --broadcast 127.255.255.255

[THÀNH VIÊN C] phụ trách ghép nối: khởi tạo SharedState (A), AppSignals (C), UDPDiscoveryService (A),
TCPConnectionManager (B), CommandParser + MainWindow (C) rồi khởi chạy các luồng nền.
"""

import argparse
import os
import signal
import sys
import traceback

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from core.shared_state import SharedState
from core.udp_discovery import UDPDiscoveryService
from network.tcp_manager import TCPConnectionManager
from ui.command_parser import CommandParser
from ui.main_window import MainWindow
from ui.qt_signals import AppSignals

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
MAX_NAME_LENGTH = 32


def _valid_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"'{value}' is not a valid port number") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError(f"port must be between 1 and 65535 (got {port})")
    return port


def _valid_name(value: str) -> str:
    name = value.strip()
    if not name:
        raise argparse.ArgumentTypeError("name must not be empty")
    if any(ch in name for ch in ("|", "\n", "\r")):
        raise argparse.ArgumentTypeError("name must not contain '|' or line breaks")
    if len(name) > MAX_NAME_LENGTH:
        raise argparse.ArgumentTypeError(f"name must be at most {MAX_NAME_LENGTH} characters")
    return name


def parse_arguments(argv=None) -> argparse.Namespace:
    """Phân tích tham số dòng lệnh khi khởi chạy ứng dụng."""
    parser = argparse.ArgumentParser(description="LAN Chat & File Sharing (TCP/UDP + PySide6)")
    parser.add_argument(
        "--name",
        type=_valid_name,
        required=True,
        help="Tên hiển thị của bạn trong mạng LAN (ví dụ: Quan, Minh, Huy)",
    )
    parser.add_argument(
        "--port",
        type=_valid_port,
        default=5000,
        help="Cổng TCP lắng nghe kết nối chat và truyền file (mặc định: 5000)",
    )
    parser.add_argument(
        "--udp-port",
        type=_valid_port,
        default=9999,
        help="Cổng UDP Broadcast để khám phá người dùng (mặc định: 9999)",
    )
    parser.add_argument(
        "--broadcast",
        type=str,
        default="255.255.255.255",
        help="Địa chỉ IP Broadcast (dùng 127.255.255.255 nếu test nhiều instance trên 1 máy Windows)",
    )
    return parser.parse_args(argv)


def _install_ctrl_c_handler(app: QApplication) -> QTimer:
    """
    Vòng lặp sự kiện Qt (viết bằng C++) chặn Python xử lý Ctrl+C.
    Một QTimer rỗng chạy mỗi 300ms trả quyền cho trình thông dịch để SIGINT được xử lý,
    và handler gọi app.quit() để vẫn đi qua bước dọn dẹp socket như /quit.
    """
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    timer = QTimer()
    timer.start(300)
    timer.timeout.connect(lambda: None)
    return timer


def main(argv=None) -> int:
    args = parse_arguments(argv)

    # 1. Khởi tạo Qt Application (Thread 1 - Main Thread)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("LAN Chat & File Sharing")
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    # 2. Khởi tạo dữ liệu dùng chung (Thành viên A) và cầu nối tín hiệu Qt (Thành viên C)
    shared_state = SharedState(my_name=args.name, my_tcp_port=args.port)
    signals = AppSignals()

    # 3. Khởi tạo các dịch vụ mạng nền (Thành viên A & Thành viên B)
    udp_service = UDPDiscoveryService(
        shared_state=shared_state,
        signals=signals,
        udp_port=args.udp_port,
        broadcast_ip=args.broadcast,
    )
    tcp_manager = TCPConnectionManager(
        shared_state=shared_state,
        signals=signals,
        listen_port=args.port,
        download_dir=DOWNLOAD_DIR,
    )

    # 4. Khởi tạo bộ phân tích lệnh và cửa sổ chính PySide6 (Thành viên C)
    command_parser = CommandParser(
        shared_state=shared_state,
        udp_service=udp_service,
        tcp_manager=tcp_manager,
        signals=signals,
        on_quit_callback=app.quit,
    )
    window = MainWindow(
        shared_state=shared_state,
        command_parser=command_parser,
        signals=signals,
    )

    # 5. Khởi chạy các luồng nền (Threads 2, 3, 4) và hiển thị GUI
    try:
        tcp_manager.start_server()
        signals.system_notification.emit(f"[*] Listening on TCP port {args.port}")
        udp_service.start()
        signals.system_notification.emit(
            f"[*] Broadcasting presence on UDP port {args.udp_port} (to {args.broadcast})"
        )
    except OSError as exc:
        # Ví dụ hay gặp: cổng TCP đã bị tiến trình khác chiếm (WinError 10048).
        traceback.print_exc()
        command_parser.shutdown()
        QMessageBox.critical(
            None,
            "LAN Chat - Network error",
            f"Could not start networking on TCP port {args.port} / UDP port {args.udp_port}:\n\n{exc}\n\n"
            "Try another --port, or check that no other instance is using it.",
        )
        return 1

    window.show()
    ctrl_c_timer = _install_ctrl_c_handler(app)

    exit_code = app.exec()

    # 6. Dọn dẹp tài nguyên khi đóng ứng dụng (idempotent: không chạy lại nếu /quit hoặc nút X đã dọn)
    ctrl_c_timer.stop()
    command_parser.shutdown()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
