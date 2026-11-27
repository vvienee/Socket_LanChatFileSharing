"""
[THÀNH VIÊN B] - Dịch vụ truyền và nhận file qua TCP (Thread 06 - File Sender).
Đảm bảo các yêu cầu:
01. Gửi file trong luồng riêng biệt để không làm đứng khung chat.
02. Cập nhật phần trăm tiến độ (%) lên GUI thông qua AppSignals.
03. Lưu file nhận được vào thư mục "downloads/".
04. Nếu quá trình nhận bị ngắt quãng giữa chừng, tự động xóa file dở dang (partial file).
"""

import os
import socket
import tempfile
import threading
import time
from typing import Optional
from core.models import ChatMessage
from core.shared_state import SharedState
from network.protocol import encode_file_header, recv_exact


class FileTransferService:
    """
    Xử lý truyền file bất đồng bộ (Thread 06) và nhận luồng byte file từ TCP socket.
    """

    CHUNK_SIZE = 65536  # 64 KB mỗi lần đọc/ghi.

    def __init__(
        self,
        shared_state: SharedState,
        signals: object,
        download_dir: str = "downloads",
    ) -> None:
        self.shared_state = shared_state
        self.signals = signals
        self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok = True)

    def start_send_file_thread(
        self,
        peer_id: str,
        filepath: str,
        sock: socket.socket,
        send_lock: threading.Lock,
    ) -> None:
        """
        Khởi tạo và chạy Thread 06 (File Sender) để gửi file tới `peer_id`.
        """

        if not os.path.isfile(filepath):
            self.signals.system_notification.emit(
                f"[!] Lỗi gửi file: Không tìm thấy tệp \"{filepath}\"."
            )
            return

        worker = threading.Thread(
            target = self._send_file_worker,
            args = (peer_id, filepath, sock, send_lock),
            name = f"FileSender-{peer_id}",
            daemon = True,
        )
        worker.start()

    def _send_file_worker(
        self,
        peer_id: str,
        filepath: str,
        sock: socket.socket,
        send_lock: threading.Lock,
    ) -> None:
        """
        [Thread 06 - File Sender Worker]
        """

        # os.path.basename(filename): lấy tên file gốc, bỏ đường dẫn cha.
        filename = os.path.basename(filepath)
        try:
            filesize = os.path.getsize(filepath)
        except OSError as exc:
            self.signals.system_notification.emit(
                f"[!] Không thể đọc kích thước file \"{filename}\": {exc}."
            )
            return

        size_mb = filesize / (1024 * 1024)
        self.signals.system_notification.emit(
            f"[*] Sending \"{filename}\" ({size_mb:.2f} MB) ..."
        )
        self.signals.file_progress_updated.emit(peer_id, filename, 0)

        sent_bytes = 0
        last_reported_percent = -1

        try:
            # Dùng send_lock bao trọn 01 frame FILE để tránh tin nhắn chat ("MSG|") chèn ngang vào giữa luồng byte file.
            with send_lock:
                header = encode_file_header(filename, filesize)
                sock.sendall(header)

                with open(filepath, "rb") as f:
                    while True:
                        chunk = f.read(self.CHUNK_SIZE)
                        if not chunk: break

                        sock.sendall(chunk)
                        sent_bytes += len(chunk)

                        percent = int((sent_bytes * 100) / filesize) if filesize > 0 else 100
                        if percent != last_reported_percent:
                            self.signals.file_progress_updated.emit(peer_id, filename, percent)
                            last_reported_percent = percent

            if filesize == 0:
                self.signals.file_progress_updated.emit(peer_id, filename, 100)

            self.signals.system_notification.emit(
                f"[*] Sent {filename} (100%) Done."
            )
        except (OSError, ConnectionError) as exc:
            self.signals.file_progress_updated.emit(peer_id, filename, -1)
            self.signals.system_notification.emit(
                f"[!] Truyền file \"{filename}\" bị gián đoạn: {exc}."
            )

    def _get_unique_save_path(self, filename: str, target_dir: Optional[str] = None) -> str:
        """
        Tạo đường dẫn lưu file trong thư mục đích (mặc định là \"downloads/\"). Nếu đã tồn tại file trùng tên,
        tự động thêm hậu tố (1), (2),... để tránh ghi đè dữ liệu cũ.
        """

        base_dir = target_dir or self.download_dir
        safe_name = os.path.basename(filename) or "received_file"
        os.makedirs(base_dir, exist_ok = True)

        candidate = os.path.join(base_dir, safe_name)
        if not os.path.exists(candidate):
            return candidate

        stem, ext = os.path.splitext(safe_name)
        counter = 1
        while True:
            candidate = os.path.join(base_dir, f"{stem}({counter}){ext}")
            if not os.path.exists(candidate):
                return candidate
            counter += 1

    def receive_file_stream(
        self,
        conn: socket.socket,
        peer_id: str,
        filename: str,
        filesize: int,
    ) -> None:
        """
        Được gọi từ Thread 05 (TCP Receiver) khi gặp header \"FILE|<filename>|<filesize>|\".
        """

        stage_mode = bool(getattr(self.signals, "stage_incoming_files", False))
        target_dir = (
            os.path.join(tempfile.gettempdir(), "lanchat_incoming_cache")
            if stage_mode
            else self.download_dir
        )
        save_path = self._get_unique_save_path(filename, target_dir = target_dir)
        saved_name = os.path.basename(save_path)
        display_name = os.path.basename(filename) or saved_name
        received_bytes = 0
        last_reported_percent = -1
        completed = False

        self.signals.system_notification.emit(
            f"[*] Receiving file \"{saved_name}\" ({filesize} bytes)..."
        )
        self.signals.file_progress_updated.emit(peer_id, saved_name, 0)

        try:
            with open(save_path, "wb") as f:
                remaining = filesize
                while remaining > 0:
                    to_read = min(self.CHUNK_SIZE, remaining)
                    chunk = recv_exact(conn, to_read)
                    f.write(chunk)
                    received_bytes += len(chunk)
                    remaining -= len(chunk)

                    percent = int((received_bytes * 100) / filesize) if filesize > 0 else 100
                    if percent != last_reported_percent:
                        self.signals.file_progress_updated.emit(peer_id, saved_name, percent)
                        last_reported_percent = percent

            if filesize == 0:
                self.signals.file_progress_updated.emit(peer_id, saved_name, 100)

            completed = True
            if stage_mode:
                peer_info = self.shared_state.find_peer(peer_id)
                sender_name = peer_info.name if peer_info else peer_id
                file_msg = ChatMessage(
                    sender_name = sender_name,
                    sender_id = peer_id,
                    content = display_name,
                    timestamp = time.time(),
                    is_system = False,
                    is_file = True,
                    file_name = display_name,
                    file_size = filesize,
                    file_path = save_path,
                )
                unread = self.shared_state.append_message(peer_id, file_msg)
                self.signals.chat_message_received.emit(peer_id, file_msg)
                if unread > 0:
                    self.signals.peer_list_updated.emit()
            else:
                self.signals.system_notification.emit(
                    f"[*] File \"{saved_name}\" saved to \"{self.download_dir}/\""
                )
        except Exception as exc:
            # Xóa file dở dang nếu quá trình nhận bị lỗi hoặc đứt kết nối giữa chừng.
            if os.path.exists(save_path):
                try:
                    os.remove(save_path)
                except OSError:
                    pass
            if not completed:
                self.signals.file_progress_updated.emit(peer_id, saved_name, -1)
                self.signals.system_notification.emit(
                    f"[!] Lỗi nhận file \"{saved_name}\" (đã xóa file lỗi): {exc}."
                )
            raise