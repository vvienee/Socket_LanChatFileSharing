"""
[THÀNH VIÊN B] - Quản lý kết nối TCP P2P và các luồng nhận/gửi dữ liệu.
Đảm nhận:
- Thread 04 (TCP Acceptor): Lắng nghe kết nối TCP mới từ các peer khác.
- Thread 05 (TCP Receiver - một luồng cho mỗi peer): Đọc khung tin MSG, FILE, BYE từ socket của peer đó.
"""

import socket
import threading
import time
from typing import Dict, Optional
from core.models import ChatMessage, PeerInfo
from core.shared_state import SharedState
from network.file_transfer import FileTransferService
from network.protocol import (
    FRAME_BYE,
    FRAME_FILE,
    FRAME_MSG,
    ENCODING,
    encode_bye,
    encode_msg,
    read_frame_header,
    recv_exact,
)


class TCPConnectionManager:
    """
    Quản lý vòng đời của TCP Server (Acceptor) và các kết nối TCP P2P tới từng peer.
    """

    def __init__(
        self,
        shared_state: SharedState,
        signals: object,
        listen_port: int,
        download_dir: str = "downloads",
    ) -> None:
        self.shared_state = shared_state
        self.signals = signals
        self.listen_port = listen_port
        self.download_dir = download_dir

        self._running = False
        self._server_sock: Optional[socket.socket] = None
        self._acceptor_thread: Optional[threading.Thread] = None

        # Bảo vệ bảng kết nối các socket đang mở: key là peer_id ("<ip>:<tcp_port>").
        self._conn_lock = threading.Lock()
        self._connections: Dict[str, socket.socket] = {}

        # Khóa gửi dữ liệu cho từng peer để tránh 02 luồng ghi đè byte lên cùng 01 socket.
        self._send_locks: Dict[str, threading.Lock] = {}

        # Dịch vụ truyền file (Thread 06).
        self.file_service = FileTransferService(
            shared_state = self.shared_state,
            signals = self.signals,
            download_dir = self.download_dir,
        )

    def start_server(self) -> None:
        """
        Khởi tạo TCP Server socket tại cổng \"self.listen_port\" và bắt đầu chạy Thread 04 (TCP Acceptor).
        """

        if self._running:
            return

        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # SOCK_STREAM --> TCP.
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(("", self.listen_port))
        server_sock.listen(16) # server listens to 16 clients (max).

        self._server_sock = server_sock
        self._running = True

        self._acceptor_thread = threading.Thread(
            target = self._acceptor_loop,
            name = f"TCPAcceptor-{self.listen_port}",
            daemon = True,
        )
        self._acceptor_thread.start()

    def _register_connection(self, peer_id: str, sock: socket.socket) -> None:
        """
        Đăng ký socket và send_lock cho một peer_id vào bảng quản lý an toàn luồng.
        Nếu đã tồn tại socket cũ cùng peer_id, đóng socket cũ trước khi thay thế.
        """

        old_sock: Optional[socket.socket] = None
        with self._conn_lock:
            if peer_id in self._connections and self._connections[peer_id] is not sock:
                old_sock = self._connections[peer_id]

            self._connections[peer_id] = sock

            if peer_id not in self._send_locks:
                self._send_locks[peer_id] = threading.Lock()

        if old_sock is not None:
            try:
                old_sock.close()
            except OSError:
                pass

    def _resolve_peer_from_ip(self, remote_ip: str, remote_port: int) -> tuple[str, str]:
        """
        Ánh xạ địa chỉ IP kết nối đến với danh sách PeerInfo đã biết qua UDP Discovery
        để lấy đúng \"peer_id\" (<ip>:<tcp_port>) và tên hiển thị.
        """

        for p in self.shared_state.get_online_peers():
            if p.ip == remote_ip:
                # Nếu chưa có kết nối TCP nào với peer này, ưu tiên ánh xạ về peer_id chuẩn.
                with self._conn_lock:
                    if p.peer_id not in self._connections:
                        return (p.peer_id, p.name)

        fallback_id = f"{remote_ip}:{remote_port}"
        return (fallback_id, fallback_id)

    def connect_to_peer(self, peer: PeerInfo) -> bool:
        """
        Mở kết nối TCP chủ động tới \"peer\" (khi người dùng gõ \"/chat <name|number>\" hoặc click trên GUI).
        """

        with self._conn_lock:
            existing = self._connections.get(peer.peer_id)
            if existing is not None:
                return True

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # SOCK_STREAM --> TCP.
        sock.settimeout(5.0)

        try:
            sock.connect((peer.ip, peer.tcp_port))
            # Chuyển về chế độ blocking vô thời hạn sau khi kết nối thành công để chờ nhận tin.
            sock.settimeout(None)
        except (OSError, socket.timeout) as exc:
            try:
                sock.close()
            except OSError:
                pass
            self.signals.system_notification.emit(
                f"[!] Không thể kết nối tới {peer.name} ({peer.peer_id}): {exc}."
            )
            return False

        self._register_connection(peer.peer_id, sock)

        recv_thread = threading.Thread(
            target = self._receiver_loop,
            args = (sock, peer.peer_id),
            name = f"TCPReceiver-{peer.peer_id}",
            daemon = True,
        )
        recv_thread.start()
        return True

    def send_text_message(self, peer_id: str, text: str) -> bool:
        """
        Đóng gói tin nhắn bằng \"protocol.encode_msg(text)\" và gửi qua socket của \"peer_id\".
        Trả về True nếu gửi thành công, False nếu lỗi kết nối.
        """

        with self._conn_lock:
            sock = self._connections.get(peer_id)
            send_lock = self._send_locks.get(peer_id)

        if sock is None or send_lock is None:
            self.signals.system_notification.emit(
                f"[!] Chưa có kết nối TCP tới {peer_id}."
            )
            return False

        frame = encode_msg(text)
        try:
            with send_lock:
                sock.sendall(frame)
            return True
        except OSError as exc:
            self.signals.system_notification.emit(
                f"[!] Gửi tin nhắn thất bại tới {peer_id}: {exc}."
            )
            self._cleanup_peer(peer_id, sock, reason = "Mất kết nối khi gửi tin nhắn")
            return False

    def send_file_async(self, peer_id: str, filepath: str) -> None:
        """
        Gọi \"self.file_service.start_send_file_thread(...)\" để truyền file trên Thread 06
        mà không làm nghẽn việc gửi/nhận tin nhắn chat.
        """

        with self._conn_lock:
            sock = self._connections.get(peer_id)
            send_lock = self._send_locks.get(peer_id)

        if sock is None or send_lock is None:
            self.signals.system_notification.emit(
                f"[!] Chưa kết nối tới {peer_id}. Hãy dùng /chat trước khi gửi file."
            )
            return

        self.file_service.start_send_file_thread(
            peer_id = peer_id,
            filepath = filepath,
            sock = sock,
            send_lock = send_lock,
        )

    def disconnect_peer(self, peer_id: str) -> None:
        """
        Ngắt kết nối với 01 peer cụ thể (khi người dùng gõ \"/leave\"):
        Gửi khung \"BYE|\" và đóng socket của peer đó.
        """

        with self._conn_lock:
            sock = self._connections.pop(peer_id, None)
            send_lock = self._send_locks.pop(peer_id, None)

        if sock is None:
            return

        try:
            if send_lock is not None:
                with send_lock:
                    sock.sendall(encode_bye())
            else:
                sock.sendall(encode_bye())
        except OSError:
            pass
        finally:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

            try:
                sock.close()
            except OSError:
                pass

    def stop_all(self) -> None:
        """
        Đóng TCP Acceptor và gửi \"BYE|\" tới toàn bộ các peer đang kết nối khi thoát ứng dụng (\"/quit\").
        """

        self._running = False

        if self._server_sock is not None:
            try:
                self._server_sock.close()
            except OSError:
                pass
            self._server_sock = None

        with self._conn_lock:
            peer_ids = list(self._connections.keys())

        for pid in peer_ids:
            self.disconnect_peer(pid)

    def _cleanup_peer(
        self,
        peer_id: str,
        target_sock: socket.socket,
        reason: str,
        notify_ui: bool = True,
    ) -> None:
        """
        Dọn dẹp socket khi peer ngắt kết nối (chỉ xóa nếu socket trong bảng khớp với target_sock).
        """

        removed = False
        with self._conn_lock:
            current_sock = self._connections.get(peer_id)
            if current_sock is target_sock:
                self._connections.pop(peer_id, None)
                self._send_locks.pop(peer_id, None)
                removed = True

        try:
            target_sock.close()
        except OSError:
            pass

        if removed and notify_ui:
            self.signals.peer_disconnected.emit(peer_id, reason)

    def _acceptor_loop(self) -> None:
        """
        [Thread 04 - TCP Acceptor]
        Vòng lặp chờ \"self._server_sock.accept()\".
        Mỗi khi có kết nối mới đến, khởi tạo một luồng \"_receiver_loop\" (Thread 05) cho kết nối đó.
        """

        while self._running and self._server_sock is not None:
            try:
                conn, addr = self._server_sock.accept()
            except OSError:
                # Socket server bị đóng khi gọi stop_all()
                break

            remote_ip, remote_port = addr[0], addr[1]
            peer_id, _ = self._resolve_peer_from_ip(remote_ip, remote_port)
            self._register_connection(peer_id, conn)

            recv_thread = threading.Thread(
                target = self._receiver_loop,
                args = (conn, peer_id),
                name = f"TCPReceiver-In-{peer_id}",
                daemon = True,
            )
            recv_thread.start()

    def _receiver_loop(self, conn: socket.socket, peer_id: str) -> None:
        """
        [Thread 05 - TCP Receiver (mỗi peer 01 luồng)]
        Vòng lặp đọc khung dữ liệu từ \"conn\" bằng \"protocol.read_frame_header(conn)\".
        """

        disconnect_reason = "Peer đã đóng kết nối."
        try:
            while self._running:
                frame_type, args = read_frame_header(conn)

                if frame_type == FRAME_BYE:
                    disconnect_reason = "Peer đã rời khỏi cuộc trò chuyện (/leave)."
                    break

                elif frame_type == FRAME_MSG:
                    msg_len = int(args[0])
                    payload = recv_exact(conn, msg_len)
                    text = payload.decode(ENCODING)

                    peer_info = self.shared_state.find_peer(peer_id)
                    sender_name = peer_info.name if peer_info else peer_id

                    chat_msg = ChatMessage(
                        sender_name = sender_name,
                        sender_id = peer_id,
                        content = text,
                        timestamp = time.time(),
                        is_system = False,
                    )

                    unread = self.shared_state.append_message(peer_id, chat_msg)
                    self.signals.chat_message_received.emit(peer_id, chat_msg)

                    # Nếu người dùng đang chat với người khác, hiển thị thông báo số tin chưa đọc.
                    if unread > 0:
                        self.signals.system_notification.emit(
                            f"[*] New message from {sender_name} ({unread} unread)."
                        )
                        self.signals.peer_list_updated.emit()

                elif frame_type == FRAME_FILE:
                    filename = args[0]
                    filesize = int(args[1])
                    self.file_service.receive_file_stream(
                        conn = conn,
                        peer_id = peer_id,
                        filename = filename,
                        filesize = filesize,
                    )

        except (ConnectionError, OSError, ValueError, UnicodeDecodeError) as exc:
            disconnect_reason = f"Ngắt kết nối ({exc})"

        finally:
            self._cleanup_peer(peer_id, conn, reason=disconnect_reason, notify_ui=self._running)