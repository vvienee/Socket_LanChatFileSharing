"""
Script kiểm thử độc lập dành cho [THÀNH VIÊN A].
Dùng để test `SharedState` và `UDPDiscoveryService` trên Terminal mà không cần chờ GUI của C hay TCP của B.
Cách chạy:
    python -m tests.mock_a_discovery --name Alice --port 5001
    python -m tests.mock_a_discovery --name Bob --port 5002
"""


class DummySignal:
    """Giả lập một Signal của PySide6 để in trực tiếp ra console khi Thành viên A tự test."""
    def __init__(self, label: str) -> None:
        self.label = label

    def emit(self, *args: object) -> None:
        print(f"[DummySignal:{self.label}] {args}")


class DummyAppSignals:
    """Bộ Signals giả lập dành cho Thành viên A."""
    def __init__(self) -> None:
        self.peer_list_updated = DummySignal("peer_list_updated")
        self.system_notification = DummySignal("system_notification")


def main() -> None:
    """
    TODO [Thành viên A]:
    Khởi tạo SharedState + UDPDiscoveryService với DummyAppSignals để kiểm thử:
    1. Phát gói tin HELLO mỗi 3s.
    2. Nhận gói tin từ instance khác.
    3. Tự động xóa peer sau 10s khi tắt một cửa sổ terminal.
    """
    print("[Mock Test A] Skeleton sẵn sàng. Thành viên A viết kịch bản test UDP Discovery tại đây.")


if __name__ == "__main__":
    main()
