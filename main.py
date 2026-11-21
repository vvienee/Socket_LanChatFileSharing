"""
Entry Point chính của ứng dụng LAN Chat & File Sharing (P2P UDP + TCP với giao diện PySide6).
Ví dụ khởi chạy:
    python main.py --name Quan --port 5001
    python main.py --name Minh --port 5002 --broadcast 127.255.255.255
"""

import argparse
import sys
from PySide6.QtWidgets import QApplication

from core.shared_state import SharedState
from core.udp_discovery import UDPDiscoveryService
from network.tcp_manager import TCPConnectionManager
from ui.command_parser import CommandParser
from ui.main_window import MainWindow
from ui.qt_signals import AppSignals


def parse_arguments() -> argparse.Namespace:
    """Phân tích tham số dòng lệnh khi khởi chạy ứng dụng."""
    parser = argparse.ArgumentParser(description="LAN Chat & File Sharing (TCP/UDP + PySide6)")
    parser.add_argument(
        "--name",
        type=str,
        required=True,
        help="Tên hiển thị của bạn trong mạng LAN (ví dụ: Quan, Minh, Huy)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Cổng TCP lắng nghe kết nối chat và truyền file (mặc định: 5000)",
    )
    parser.add_argument(
        "--udp-port",
        type=int,
        default=9999,
        help="Cổng UDP Broadcast để khám phá người dùng (mặc định: 9999)",
    )
    parser.add_argument(
        "--broadcast",
        type=str,
        default="255.255.255.255",
        help="Địa chỉ IP Broadcast (dùng 127.255.255.255 nếu test nhiều instance trên 1 máy Windows)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    # 1. Khởi tạo Qt Application (Thread 1 - Main Thread)
    app = QApplication(sys.argv)

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
        download_dir="downloads",
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
    tcp_manager.start_server()
    udp_service.start()
    window.show()

    exit_code = app.exec()

    # 6. Dọn dẹp tài nguyên khi đóng ứng dụng
    udp_service.stop()
    tcp_manager.stop_all()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
