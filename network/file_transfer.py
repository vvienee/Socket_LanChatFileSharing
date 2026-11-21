"""
[THÀNH VIÊN B] - Dịch vụ truyền và nhận file qua TCP (Thread 6 - File Sender).
Đảm bảo các yêu cầu:
1. Gửi file trong luồng riêng biệt để không làm đứng khung chat.
2. Cập nhật phần trăm tiến độ (%) lên GUI thông qua AppSignals.
3. Lưu file nhận được vào thư mục `downloads/`.
4. Nếu quá trình nhận bị ngắt quãng giữa chừng, tự động xóa file dở dang (partial file).
"""

import socket
import threading
from core.shared_state import SharedState


class FileTransferService:
    """
    Xử lý truyền file bất đồng bộ (Thread 6) và nhận luồng byte file từ TCP socket.
    """

    CHUNK_SIZE = 65536  # 64 KB mỗi lần đọc/ghi

    def __init__(
        self,
        shared_state: SharedState,
        signals: object,
        download_dir: str = "downloads",
    ) -> None:
        self.shared_state = shared_state
        self.signals = signals
        self.download_dir = download_dir

    def start_send_file_thread(
        self,
        peer_id: str,
        filepath: str,
        sock: socket.socket,
        send_lock: threading.Lock,
    ) -> None:
        """
        Khởi tạo và chạy **Thread 6 (File Sender)** để gửi file tới `peer_id`.
        - Kiểm tra file có tồn tại hay không trước khi mở luồng; nếu không, báo lỗi qua `signals.system_notification`.
        TODO [Thành viên B]: Tạo threading.Thread(target=self._send_file_worker, ..., daemon=True).start().
        """
        pass

    def _send_file_worker(
        self,
        peer_id: str,
        filepath: str,
        sock: socket.socket,
        send_lock: threading.Lock,
    ) -> None:
        """
        [Thread 6 - File Sender Worker]
        1. Lấy kích thước file và tên file gốc (os.path.basename).
        2. Gửi header `FILE|<filename>|<size>|` và toàn bộ nội dung file theo từng chunk.
        3. Cập nhật tiến độ (%) qua `self.signals.file_progress_updated.emit(peer_id, filename, percent)`.
        4. Xử lý ngoại lệ nếu mất kết nối giữa chừng.
        TODO [Thành viên B]: Hiện thực logic gửi file và báo cáo tiến độ.
        """
        pass

    def receive_file_stream(
        self,
        conn: socket.socket,
        peer_id: str,
        filename: str,
        filesize: int,
    ) -> None:
        """
        Được gọi từ Thread 5 (TCP Receiver) khi gặp header `FILE|<filename>|<filesize>|`.
        1. Tạo đường dẫn lưu an toàn trong thư mục `self.download_dir` (xử lý trùng tên nếu cần).
        2. Đọc từng chunk từ `conn` cho tới khi đủ `filesize` bytes, ghi xuống đĩa và phát tín hiệu tiến độ `%`.
        3. Nếu kết nối đứt trước khi nhận đủ `filesize` bytes:
           - Đóng file và **XÓA file lỗi (partial file)** bằng `os.remove()`.
           - Thông báo lỗi lên giao diện qua `self.signals.system_notification.emit(...)`.
        TODO [Thành viên B]: Hiện thực logic nhận file và dọn dẹp file lỗi.
        """
        pass
